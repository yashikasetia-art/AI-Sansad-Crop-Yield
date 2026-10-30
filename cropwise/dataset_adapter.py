"""Normalize common agricultural table layouts to crop-year yield records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd


IDENTITY_FIELDS = ("Crop", "Season", "State", "District")
AGGREGATE_CROPS = {
    "cereals",
    "nutri/coarse cereals",
    "shree anna /nutri cereals",
    "other pulses",
    "total pulses",
    "total food grains",
    "total oil seeds",
    "jute & mesta",
}


@dataclass(frozen=True)
class AdaptedDataset:
    data: pd.DataFrame
    issues: tuple[str, ...]
    detected_layout: str


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _flatten_columns(columns: pd.Index) -> list[str]:
    flattened: list[str] = []
    for column in columns:
        parts = column if isinstance(column, tuple) else (column,)
        values = [str(part).strip() for part in parts if str(part).strip() and not str(part).startswith("Unnamed:")]
        flattened.append("-".join(values) if values else "")
    return flattened


def _read_excel(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None)
    header_row = None
    for row_index, row in raw.iterrows():
        values = {_key(value) for value in row.dropna()}
        if "year" in values and "season" in values:
            header_row = int(row_index)
            break
    if header_row is None:
        return pd.read_excel(path, sheet_name=0)
    frame = pd.read_excel(path, sheet_name=0, header=[header_row - 1, header_row])
    frame.columns = _flatten_columns(frame.columns)
    if "Year" in frame.columns:
        frame["Year"] = frame["Year"].ffill()
    if "Season" in frame.columns:
        frame = frame.loc[frame["Season"].notna()].copy()
    return frame


def load_table(path: str | Path) -> pd.DataFrame:
    """Load CSV/XLSX input, including the metadata header in the DA&FW workbook."""
    source = Path(path)
    if source.suffix.casefold() == ".xlsx":
        frame = _read_excel(source)
    elif source.suffix.casefold() == ".csv":
        frame = pd.read_csv(source, low_memory=False)
    else:
        raise ValueError("Only CSV and XLSX files are supported")
    frame.columns = _flatten_columns(frame.columns)
    return frame


def _find_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    by_key = {_key(column): str(column) for column in frame.columns}
    for alias in aliases:
        if _key(alias) in by_key:
            return by_key[_key(alias)]
    return None


def _normalize_crop(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def adapt_yield_data(
    frame: pd.DataFrame,
    column_map: Mapping[str, str] | None = None,
    yield_unit: str | None = None,
) -> AdaptedDataset:
    """Convert common wide or long layouts without filling missing values.

    `column_map` may explicitly map semantic fields (`crop`, `year`, `yield`,
    `season`, `state`, `district`) to exact input column names.
    """
    source = frame.copy()
    source.columns = _flatten_columns(source.columns)
    mapping = dict(column_map or {})
    issues: list[str] = []

    def selected(field: str, aliases: tuple[str, ...]) -> str | None:
        explicit = mapping.get(field)
        if explicit:
            if explicit not in source.columns:
                raise ValueError(f"Mapped {field!r} column {explicit!r} was not found")
            return explicit
        return _find_column(source, aliases)

    crop_col = selected("crop", ("Crop", "Crop Name", "Commodity"))
    year_col = selected("year", ("Year", "Crop Year", "CropYear", "YearKey"))
    yield_col = selected("yield", ("Yield", "Crop Yield", "Yield Kg/Ha"))
    season_col = selected("season", ("Season",))
    state_col = selected("state", ("State", "State Name", "StateName"))
    district_col = selected("district", ("District", "District Name", "DistrictName"))
    identity: dict[str, str] = {}
    for label, column in (("Crop", crop_col), ("Season", season_col), ("State", state_col), ("District", district_col)):
        if column:
            identity[label] = column

    if crop_col and year_col and yield_col:
        columns = list(identity.values()) + [year_col, yield_col]
        result = source[columns].copy()
        result = result.rename(columns={crop_col: "Crop", year_col: "Year", yield_col: "Yield"})
        if season_col:
            result = result.rename(columns={season_col: "Season"})
        if state_col:
            result = result.rename(columns={state_col: "State"})
        if district_col:
            result = result.rename(columns={district_col: "District"})
        layout = "long"
    elif crop_col and any(re.match(r"(?i)^yield[-_ ]", str(column)) for column in source.columns):
        yield_columns = [column for column in source.columns if re.match(r"(?i)^yield[-_ ]", str(column))]
        id_columns = list(dict.fromkeys(identity.values()))
        melted = source.melt(id_vars=id_columns, value_vars=yield_columns, var_name="_year", value_name="Yield")
        melted["Year"] = melted["_year"].astype(str).str.replace(r"(?i)^yield[-_ ]", "", regex=True)
        melted = melted.drop(columns="_year")
        result = melted.rename(columns={crop_col: "Crop", season_col: "Season", state_col: "State", district_col: "District"})
        layout = "crop-year-wide"
    else:
        if not year_col:
            raise ValueError("Could not identify a year column or year-suffixed Yield columns")
        wide_yields = [column for column in source.columns if re.match(r"(?i)^.+[-_ ]yield$", str(column))]
        if not wide_yields:
            raise ValueError("Could not identify yield observations; map the crop, year, and yield columns")
        id_columns = [year_col] + [column for column in identity.values() if column != year_col]
        records: list[pd.DataFrame] = []
        for column in wide_yields:
            crop_name = re.sub(r"(?i)[-_ ]yield$", "", str(column)).strip()
            part = source[id_columns + [column]].copy()
            part = part.rename(columns={year_col: "Year", column: "Yield"})
            part["Crop"] = crop_name
            part = part.rename(columns={season_col: "Season", state_col: "State", district_col: "District"})
            records.append(part)
        result = pd.concat(records, ignore_index=True)
        layout = "crop-metric-wide"

    result["Crop"] = result["Crop"].map(_normalize_crop)
    result["Year"] = result["Year"].astype("string").str.strip()
    result["Yield"] = pd.to_numeric(result["Yield"], errors="coerce")
    missing_yields = int(result["Yield"].isna().sum())
    if missing_yields:
        issues.append(f"{missing_yields} rows have missing or non-numeric yield and remain excluded from calculations")
    negative_count = int((result["Yield"] < 0).sum())
    if negative_count:
        issues.append(f"{negative_count} negative yields were excluded as invalid observations")
        result = result.loc[result["Yield"] >= 0].copy()
    result = result.dropna(subset=["Crop", "Year", "Yield"])
    result = result.loc[result["Crop"].ne("") & result["Year"].ne("")].copy()
    if yield_unit:
        result["YieldUnit"] = yield_unit
    result = result.reset_index(drop=True)
    return AdaptedDataset(result, tuple(issues), layout)


def select_season(data: pd.DataFrame, season: str = "Total") -> pd.DataFrame:
    """Select one season; annual analysis never silently sums seasonal records."""
    if "Season" not in data.columns:
        return data.copy()
    available = data["Season"].dropna().astype(str).str.strip().str.casefold()
    matches = data["Season"].astype("string").str.strip().str.casefold().eq(season.casefold())
    if not matches.any():
        if season.casefold() == "total":
            raise ValueError("Annual analysis requires source Total observations; seasonal rows will not be combined")
        raise ValueError(f"Requested season {season!r} is not available")
    if season.casefold() == "total" and available.nunique() > 1:
        return data.loc[matches].copy()
    return data.loc[matches].copy()


def is_aggregate_crop(crop: object) -> bool:
    label = _normalize_crop(crop).casefold()
    return label.startswith("total ") or label in AGGREGATE_CROPS
