"""Local dataset loading and database-backed analytics helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.db import CropwiseDatabase

from .analysis import analyze_variability
from .dataset_adapter import adapt_yield_data, load_table, select_season


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_SOURCE = ROOT / "All-India_-Year-wise-Crop-Area,-Production-&-Yield.csv"
STATE_SOURCE = ROOT / "Crop-Profile_-State-wise-Area,-Production-&-Yield-of-All-Crops,-(2021-22-to-2025-26).csv"
DISTRICT_SOURCE = ROOT / "DES-District-Data-For-2024-25.csv"


def load_yield_file(path: str | Path, *, annual_total: bool = True, yield_unit: str | None = None) -> pd.DataFrame:
    """Adapt a supported source file and optionally select source Total rows."""
    adapted = adapt_yield_data(load_table(path), yield_unit=yield_unit)
    data = adapted.data
    if annual_total and "Season" in data:
        data = select_season(data, "Total")
    return data.reset_index(drop=True)


def ensure_local_database(database: CropwiseDatabase | None = None) -> tuple[CropwiseDatabase, dict[str, object]]:
    """Initialize SQLite and seed it once from the long-term annual source."""
    store = database or CropwiseDatabase()
    store.initialize()
    existing = store.counts()["yield_records"]
    if existing:
        return store, {"source": "SQLite database", "seeded": False, "rows": existing}
    if not HISTORICAL_SOURCE.exists():
        return store, {"source": "No local source available", "seeded": False, "rows": 0}

    annual = load_yield_file(HISTORICAL_SOURCE, yield_unit="Kg/Ha")
    result = store.ingest_yields(
        annual,
        source_name=HISTORICAL_SOURCE.name,
        source_path=str(HISTORICAL_SOURCE),
        reporting_status="source-reported; estimate status not independently verified",
        default_unit="Kg/Ha",
    )
    return store, {"source": HISTORICAL_SOURCE.name, "seeded": True, **result}


def saved_annual_yields(
    database: CropwiseDatabase,
    *,
    crop: str | None = None,
    state: str | None = None,
    season: str = "Total",
) -> pd.DataFrame:
    """Read annual yield records back from persistent storage."""
    return database.get_yields(crop=crop, state=state, season=season)


def variability_for_saved_data(
    database: CropwiseDatabase,
    *,
    state: str | None = None,
    season: str = "Total",
    minimum_observations: int = 5,
) -> pd.DataFrame:
    data = saved_annual_yields(database, state=state, season=season)
    return analyze_variability(data, minimum_observations=minimum_observations)


def load_state_yields(path: str | Path = STATE_SOURCE) -> pd.DataFrame:
    """Load the recent state panel without filling absent observations."""
    return load_yield_file(path, annual_total=True, yield_unit="Kg/Ha")


def load_district_yields(path: str | Path = DISTRICT_SOURCE) -> pd.DataFrame:
    """Load the one-year district snapshot for cross-sectional comparison."""
    return load_yield_file(path, annual_total=True, yield_unit="Kg/Ha")


def to_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Convert pandas/numpy values to strict JSON-compatible Python values."""
    records: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        clean: dict[str, object] = {}
        for key, value in row.items():
            if pd.isna(value):
                clean[key] = None
            elif hasattr(value, "item"):
                clean[key] = value.item()
            else:
                clean[key] = value
        records.append(clean)
    return records