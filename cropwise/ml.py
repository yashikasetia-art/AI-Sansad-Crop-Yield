"""Small-sample time-series models and explainable crop risk analysis."""

from __future__ import annotations

import time
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from .analysis import _year_number


RANDOM_STATE = 42


def _features(series: pd.DataFrame) -> pd.DataFrame:
    frame = series.sort_values("_time").copy()
    prior = frame["Yield"].shift(1)
    frame["lag_1"] = prior
    frame["lag_2"] = frame["Yield"].shift(2)
    frame["rolling_mean_3"] = prior.rolling(3, min_periods=1).mean()
    frame["year_index"] = frame["_time"] - frame["_time"].min()
    return frame.dropna(subset=["Yield", "lag_1", "lag_2", "year_index"])


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)) if len(actual) >= 2 else float("nan"),
    }


def evaluate_forecasts(
    data: pd.DataFrame,
    crop: str,
    *,
    test_fraction: float = 0.2,
    minimum_observations: int = 20,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate one-step-ahead forecasts using chronological train/validation/test splits.

    Each test prediction uses actual historical yields through the preceding
    year (rolling one-step evaluation); it never uses the target year's yield as
    a feature. A prior-year-yield baseline is reported beside both estimators.
    """
    if not 0 < test_fraction < 0.5:
        raise ValueError("test_fraction must be between 0 and 0.5")
    required = {"Crop", "Year", "Yield"}
    if not required.issubset(data.columns):
        raise ValueError(f"Required columns: {', '.join(sorted(required))}")
    series = data.loc[data["Crop"].astype(str).eq(crop), ["Year", "Yield"]].copy()
    series["Yield"] = pd.to_numeric(series["Yield"], errors="coerce")
    series = series.dropna().copy()
    series["_time"] = series["Year"].map(_year_number)
    if not np.isfinite(series["_time"]).all():
        raise ValueError("Forecasting requires years with a four-digit year component")
    if series["Year"].duplicated().any():
        raise ValueError(f"Duplicate years found for {crop}")
    features = _features(series)
    if len(series) < minimum_observations or len(features) < 12:
        return {"crop": crop, "status": "insufficient_data", "observations": len(series), "required": minimum_observations}

    x_columns = ["lag_1", "lag_2", "rolling_mean_3", "year_index"]
    x = features[x_columns]
    y = features["Yield"].to_numpy(dtype=float)
    validation_end = int(len(features) * (1 - test_fraction))
    train_end = int(validation_end * 0.75)
    if train_end < 6 or validation_end <= train_end or len(features) - validation_end < 3:
        return {"crop": crop, "status": "insufficient_data", "observations": len(series), "required": minimum_observations}

    constructors = {
        "random_forest": lambda: RandomForestRegressor(n_estimators=250, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=1),
        "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=100, learning_rate=0.03, max_depth=2, loss="huber", random_state=RANDOM_STATE),
    }
    validation_baseline = x.iloc[train_end:validation_end]["lag_1"].to_numpy(dtype=float)
    validation_results: dict[str, dict[str, float]] = {
        "previous_year_baseline": _metrics(y[train_end:validation_end], validation_baseline)
    }
    cv_results: dict[str, float] = {}
    model_objects: dict[str, Any] = {}

    for model_name, constructor in constructors.items():
        model = constructor()
        model.fit(x.iloc[:train_end], y[:train_end])
        validation_prediction = model.predict(x.iloc[train_end:validation_end])
        validation_results[model_name] = _metrics(y[train_end:validation_end], validation_prediction)
        model_objects[model_name] = model
        if train_end >= 12:
            splitter = TimeSeriesSplit(n_splits=3)
            fold_errors: list[float] = []
            for fold_train, fold_test in splitter.split(x.iloc[:train_end]):
                fold_model = constructor()
                fold_model.fit(x.iloc[fold_train], y[fold_train])
                fold_errors.append(mean_absolute_error(y[fold_test], fold_model.predict(x.iloc[fold_test])))
            cv_results[model_name] = float(np.mean(fold_errors))

    chosen = min(validation_results, key=lambda name: validation_results[name]["mae"])
    test_x = x.iloc[validation_end:]
    test_y = y[validation_end:]
    baseline_prediction = test_x["lag_1"].to_numpy(dtype=float)
    output_metrics: dict[str, dict[str, float]] = {"previous_year_baseline": _metrics(test_y, baseline_prediction)}
    predictions: dict[str, np.ndarray] = {"previous_year_baseline": baseline_prediction}
    for model_name, constructor in constructors.items():
        final_model = constructor()
        fit_start = time.perf_counter()
        final_model.fit(x.iloc[:validation_end], y[:validation_end])
        training_seconds = time.perf_counter() - fit_start
        inference_start = time.perf_counter()
        prediction = final_model.predict(test_x)
        inference_seconds = (time.perf_counter() - inference_start) / max(len(test_x), 1)
        output_metrics[model_name] = {
            **_metrics(test_y, prediction),
            "training_seconds": float(training_seconds),
            "inference_seconds_per_observation": float(inference_seconds),
            "validation_mae": validation_results[model_name]["mae"],
            "time_series_cv_mae": cv_results.get(model_name, float("nan")),
        }
        predictions[model_name] = prediction
        model_objects[model_name] = final_model

    selected_model = model_objects.get(chosen)
    feature_importance = (
        {
            feature: float(value)
            for feature, value in zip(x_columns, getattr(selected_model, "feature_importances_", np.zeros(len(x_columns))))
        }
        if selected_model is not None
        else {}
    )
    forecast_rows = []
    for offset, (_, row) in enumerate(features.iloc[validation_end:].iterrows()):
        forecast_rows.append(
            {
                "Year": row["Year"],
                "Actual": float(test_y[offset]),
                **{name: float(values[offset]) for name, values in predictions.items()},
            }
        )

    model_path = None
    if artifact_dir is not None and selected_model is not None:
        import joblib

        destination = Path(artifact_dir)
        destination.mkdir(parents=True, exist_ok=True)
        artifact = destination / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', crop)}_{chosen}.joblib"
        joblib.dump({"model": selected_model, "features": x_columns, "crop": crop, "selected_by": "chronological validation MAE"}, artifact)
        model_path = str(artifact)

    return {
        "crop": crop,
        "status": "evaluated",
        "observations": len(series),
        "feature_observations": len(features),
        "train_count": train_end,
        "validation_count": validation_end - train_end,
        "test_count": len(test_y),
        "selected_model": chosen,
        "metrics": output_metrics,
        "validation_metrics": validation_results,
        "feature_importance": feature_importance,
        "predictions": pd.DataFrame(forecast_rows),
        "model_path": model_path,
        "evaluation_design": f"chronological split; {train_end} train, {validation_end - train_end} validation, {len(test_y)} test; validation selects the artifact; rolling one-step actual-history features",
    }


def detect_yield_anomalies(
    data: pd.DataFrame,
    *,
    minimum_observations: int = 10,
    contamination: float = 0.05,
) -> pd.DataFrame:
    """Flag unusual yields using Isolation Forest on linear-trend residuals."""
    if not 0 < contamination <= 0.2:
        raise ValueError("contamination must be in (0, 0.2]")
    records: list[pd.DataFrame] = []
    for crop, group in data.groupby("Crop", sort=False):
        frame = group[["Year", "Yield"]].copy()
        frame["Yield"] = pd.to_numeric(frame["Yield"], errors="coerce")
        frame = frame.dropna().copy()
        frame["_time"] = frame["Year"].map(_year_number)
        frame = frame.loc[np.isfinite(frame["_time"])].sort_values("_time")
        if len(frame) < minimum_observations or frame["Year"].duplicated().any():
            continue
        slope, intercept = np.polyfit(frame["_time"], frame["Yield"], 1)
        frame["TrendYield"] = intercept + slope * frame["_time"]
        frame["Residual"] = frame["Yield"] - frame["TrendYield"]
        detector = IsolationForest(contamination=contamination, random_state=RANDOM_STATE)
        frame["Anomaly"] = detector.fit_predict(frame[["Residual"]]) == -1
        frame["AnomalyScore"] = detector.decision_function(frame[["Residual"]])
        frame["Crop"] = crop
        frame["Explanation"] = np.where(frame["Anomaly"], "Yield deviates unusually from this crop's fitted historical trend", "Within fitted residual pattern")
        records.append(frame.drop(columns="_time"))
    if not records:
        return pd.DataFrame(columns=["Crop", "Year", "Yield", "TrendYield", "Residual", "Anomaly", "AnomalyScore", "Explanation"])
    return pd.concat(records, ignore_index=True)


def cluster_stability_profiles(metrics: pd.DataFrame, *, clusters: int = 3) -> pd.DataFrame:
    """Cluster crop summaries after standardizing their stability features."""
    features = ["CVPercent", "DetrendedCVPercent", "DownsideDeviation", "TrendSlopePerYear"]
    if clusters < 2:
        raise ValueError("clusters must be at least 2")
    if not set(features).issubset(metrics.columns):
        raise ValueError("Variability metrics do not contain the required clustering features")
    result = metrics.dropna(subset=features).copy()
    if len(result) <= clusters:
        raise ValueError("Need more crop profiles than requested clusters")
    scaler = StandardScaler()
    scaled = scaler.fit_transform(result[features])
    model = KMeans(n_clusters=clusters, random_state=RANDOM_STATE, n_init=20)
    result["Cluster"] = model.fit_predict(scaled)
    result["ClusterFeatureSet"] = ", ".join(features)
    return result
