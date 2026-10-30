"""Descriptive and detrended crop-yield variability metrics."""

from __future__ import annotations

import re
from typing import Sequence

import numpy as np
import pandas as pd

from .dataset_adapter import is_aggregate_crop


def _year_number(value: object) -> float:
    match = re.search(r"\d{4}", str(value))
    return float(match.group()) if match else np.nan


def annual_yield_changes(data: pd.DataFrame) -> pd.DataFrame:
    """Return consecutive year changes without dividing by zero or filling gaps."""
    required = {"Crop", "Year", "Yield"}
    if not required.issubset(data.columns):
        raise ValueError(f"Required columns: {', '.join(sorted(required))}")
    scope = [column for column in ("State", "Season", "District") if column in data]
    keys = ["Crop", *scope]
    frame = data.sort_values(keys + ["Year"]).copy()
    frame["_YearNumber"] = frame["Year"].map(_year_number)
    grouped = frame.groupby(keys, dropna=False, sort=False)
    previous = grouped["Yield"].shift(1)
    previous_year = grouped["_YearNumber"].shift(1)
    consecutive_year = frame["_YearNumber"].sub(previous_year).eq(1)
    change = (frame["Yield"] - previous).where(consecutive_year)
    frame["AnnualChange"] = change
    frame["AnnualChangePct"] = (change / previous.where(previous.ne(0))) * 100
    return frame


def _volatility_direction(residuals: np.ndarray, threshold: float) -> tuple[str, float, float]:
    midpoint = len(residuals) // 2
    early = residuals[:midpoint]
    late = residuals[midpoint:]
    if len(early) < 2 or len(late) < 2:
        return "Insufficient observations", np.nan, np.nan
    early_sd = float(np.std(early, ddof=1))
    late_sd = float(np.std(late, ddof=1))
    if early_sd == 0:
        ratio = np.inf if late_sd > 0 else 1.0
    else:
        ratio = late_sd / early_sd
    if ratio > 1 + threshold:
        direction = "Increasing volatility"
    elif ratio < 1 - threshold:
        direction = "Improving stability"
    else:
        direction = "No clear change"
    return direction, early_sd, late_sd


def analyze_variability(
    data: pd.DataFrame,
    *,
    minimum_observations: int = 5,
    classification_quantiles: tuple[float, float] = (0.33, 0.67),
    volatility_change_threshold: float = 0.15,
    exclude_aggregates: bool = True,
) -> pd.DataFrame:
    """Calculate crop stability metrics using observed yields only.

    Detrended CV is residual sample standard deviation divided by mean observed
    yield. Volatility classes use configurable empirical quantiles, not official
    government thresholds. Temporal change compares residual dispersion in the
    first and second chronological halves, with a configurable relative change.
    """
    required = {"Crop", "Year", "Yield"}
    if not required.issubset(data.columns):
        raise ValueError(f"Required columns: {', '.join(sorted(required))}")
    if minimum_observations < 2:
        raise ValueError("minimum_observations must be at least 2")
    low, high = classification_quantiles
    if not 0 < low < high < 1:
        raise ValueError("classification_quantiles must satisfy 0 < low < high < 1")
    if volatility_change_threshold < 0:
        raise ValueError("volatility_change_threshold cannot be negative")

    frame = data.copy()
    frame["Yield"] = pd.to_numeric(frame["Yield"], errors="coerce")
    frame = frame.dropna(subset=["Crop", "Year", "Yield"])
    if exclude_aggregates:
        frame = frame.loc[~frame["Crop"].map(is_aggregate_crop)]
    if frame.empty:
        return pd.DataFrame()
    frame["_time"] = frame["Year"].map(_year_number)
    frame["_sort"] = frame["_time"].fillna(pd.Series(np.arange(len(frame)), index=frame.index))
    frame = frame.sort_values("_sort")

    group_columns = ["Crop"] + [column for column in ("State", "Season", "District") if column in frame]
    rows: list[dict[str, object]] = []
    for group_key, group in frame.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        group = group.sort_values("_sort")
        identity = dict(zip(group_columns, group_key))
        if group["Year"].duplicated().any():
            raise ValueError(f"Duplicate crop/year observations detected for {identity}")
        values = group["Yield"].to_numpy(dtype=float)
        years = group["Year"].astype(str).to_numpy()
        n = len(values)
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1)) if n >= 2 else np.nan
        time = group["_time"].to_numpy(dtype=float)
        if n >= 2 and np.isfinite(time).all() and np.ptp(time) > 0:
            slope, intercept = np.polyfit(time, values, 1)
        elif n >= 2:
            slope, intercept = np.polyfit(np.arange(n, dtype=float), values, 1)
        else:
            slope, intercept = np.nan, np.nan
        trend_values = intercept + slope * (time if np.isfinite(time).all() else np.arange(n))
        residuals = values - trend_values
        residual_sd = float(np.std(residuals, ddof=1)) if n >= 2 else np.nan
        negative = residuals[residuals < 0]
        downside_deviation = float(np.sqrt(np.mean(np.minimum(residuals, 0) ** 2))) if n else np.nan
        anomaly_threshold = -2 * residual_sd if residual_sd and np.isfinite(residual_sd) else np.nan
        unusual = int(np.sum(residuals < anomaly_threshold)) if np.isfinite(anomaly_threshold) else 0
        direction, early_sd, late_sd = _volatility_direction(residuals, volatility_change_threshold)
        row: dict[str, object] = {
            **identity,
            "MeanYield": mean,
            "MedianYield": float(np.median(values)),
            "MinimumYield": float(np.min(values)),
            "MaximumYield": float(np.max(values)),
            "StandardDeviation": sd,
            "Variance": float(np.var(values, ddof=1)) if n >= 2 else np.nan,
            "Range": float(np.ptp(values)),
            "CVPercent": sd / mean * 100 if n >= 2 and mean > 0 else np.nan,
            "DetrendedCVPercent": residual_sd / mean * 100 if n >= 2 and mean > 0 else np.nan,
            "TrendSlopePerYear": float(slope) if np.isfinite(slope) else np.nan,
            "TrendDirection": "Increasing" if slope > 0 else "Declining" if slope < 0 else "Flat" if np.isfinite(slope) else "Unavailable",
            "NegativeDeviationYears": int(len(negative)),
            "AverageNegativeDeviation": float(np.mean(negative)) if len(negative) else 0.0,
            "WorstNegativeDeviation": float(np.min(negative)) if len(negative) else 0.0,
            "DownsideDeviation": downside_deviation,
            "UnusuallyPoorYears": unusual,
            "AnomalyThresholdResidual": float(anomaly_threshold) if np.isfinite(anomaly_threshold) else np.nan,
            "ObservationCount": n,
            "StartYear": years[0],
            "EndYear": years[-1],
            "VolatilityDirection": direction,
            "EarlyResidualSD": early_sd,
            "LateResidualSD": late_sd,
            "Reliability": "Insufficient" if n < minimum_observations else "Low" if n < 10 else "Moderate" if n < 20 else "Higher",
        }
        if "YieldUnit" in group:
            units = group["YieldUnit"].dropna().astype(str).unique()
            row["YieldUnit"] = units[0] if len(units) == 1 else "Mixed/unknown"
        rows.append(row)

    results = pd.DataFrame(rows)
    eligible = results["ObservationCount"] >= minimum_observations
    eligible_values = results.loc[eligible, "DetrendedCVPercent"].dropna()
    if len(eligible_values):
        lower = float(eligible_values.quantile(low))
        upper = float(eligible_values.quantile(high))
    else:
        lower = upper = np.nan

    def classify(row: pd.Series) -> str:
        if row["ObservationCount"] < minimum_observations or not np.isfinite(row["DetrendedCVPercent"]):
            return "Insufficient data"
        if row["VolatilityDirection"] == "Increasing volatility":
            return "Increasing Volatility"
        if row["VolatilityDirection"] == "Improving stability":
            return "Improving Stability"
        if row["DetrendedCVPercent"] <= lower:
            return "Stable Yield"
        if row["DetrendedCVPercent"] <= upper:
            return "Moderate Variability"
        return "High Variability"

    results["StabilityClass"] = results.apply(classify, axis=1)
    results["ClassificationLowerCV"] = lower
    results["ClassificationUpperCV"] = upper
    results["ClassificationMethod"] = f"Empirical detrended-CV quantiles {low:.2f}/{high:.2f}; volatility shift {volatility_change_threshold:.0%}"
    return results.sort_values("DetrendedCVPercent", na_position="last").reset_index(drop=True)


def rank_crops(results: pd.DataFrame, *, top_n: int = 10) -> dict[str, pd.DataFrame]:
    """Create stable/variable and risk rankings from a common eligible cohort."""
    if top_n < 1:
        raise ValueError("top_n must be positive")
    ranking_names = ("stable", "variable", "increasing_volatility", "declining_yield", "downside_risk")
    if results.empty:
        return {name: pd.DataFrame() for name in ranking_names}
    eligible = results.loc[results["StabilityClass"].ne("Insufficient data")].copy()
    if "YieldUnit" in eligible and eligible["YieldUnit"].nunique(dropna=True) > 1:
        units = eligible["YieldUnit"].fillna("unknown").nunique()
        if units > 1:
            return {"warning": pd.DataFrame({"Warning": ["Rankings omitted: yield units are not comparable across records."]})}
    stable = eligible.nsmallest(top_n, "DetrendedCVPercent")
    variable = eligible.nlargest(top_n, "DetrendedCVPercent")
    increasing = eligible.loc[eligible["VolatilityDirection"].eq("Increasing volatility")].sort_values("DetrendedCVPercent", ascending=False).head(top_n)
    declining = eligible.loc[eligible["TrendDirection"].eq("Declining")].sort_values("TrendSlopePerYear").head(top_n)
    downside = eligible.sort_values("WorstNegativeDeviation").head(top_n)
    return {"stable": stable, "variable": variable, "increasing_volatility": increasing, "declining_yield": declining, "downside_risk": downside}
