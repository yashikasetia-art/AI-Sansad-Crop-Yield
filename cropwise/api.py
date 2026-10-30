"""FastAPI endpoints for the offline-first Cropwise analytics service."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from dotenv import load_dotenv

from database.db import CropwiseDatabase, DEFAULT_DB

from .analysis import analyze_variability, rank_crops
from .dataset_adapter import adapt_yield_data, load_table, select_season
from .ml import detect_yield_anomalies, evaluate_forecasts
from .service import ensure_local_database, saved_annual_yields, to_records


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


app = FastAPI(
    title="Cropwise AI API",
    version="1.0.0",
    description="Offline-first crop-yield analytics backed by SQLite and sourced datasets.",
)


def _database() -> CropwiseDatabase:
    configured = os.getenv("CROPWISE_DB_PATH") or os.getenv("DATABASE_PATH")
    return CropwiseDatabase(configured or DEFAULT_DB)


def _ready() -> tuple[CropwiseDatabase, dict[str, object]]:
    return ensure_local_database(_database())


@app.get("/api/status")
def status() -> dict[str, Any]:
    database, source = _ready()
    return {
        "status": "ok",
        "data_source": source["source"],
        "seeded_this_request": source.get("seeded", False),
        "database_counts": database.counts(),
        "api_credentials_configured": bool(os.getenv("UPAG_USER") and os.getenv("UPAG_PASSWORD")),
    }


@app.get("/api/yields")
def yields(crop: str | None = None, state: str | None = None, season: str = "Total") -> dict[str, Any]:
    database, _ = _ready()
    data = saved_annual_yields(database, crop=crop, state=state, season=None if season.casefold() == "all" else season)
    return {"count": len(data), "records": to_records(data)}


@app.get("/api/variability")
def variability(
    state: str | None = None,
    season: str = "Total",
    minimum_observations: int = 5,
) -> dict[str, Any]:
    if minimum_observations < 2:
        raise HTTPException(status_code=422, detail="minimum_observations must be at least 2")
    database, _ = _ready()
    data = saved_annual_yields(database, state=state, season=None if season.casefold() == "all" else season)
    results = analyze_variability(data, minimum_observations=minimum_observations)
    return {
        "count": len(results),
        "classification_method": results["ClassificationMethod"].iloc[0] if not results.empty else None,
        "records": to_records(results),
    }


@app.get("/api/rankings")
def rankings(state: str | None = None, season: str = "Total", top_n: int = 10) -> dict[str, Any]:
    if top_n < 1 or top_n > 100:
        raise HTTPException(status_code=422, detail="top_n must be between 1 and 100")
    database, _ = _ready()
    data = saved_annual_yields(database, state=state, season=None if season.casefold() == "all" else season)
    results = analyze_variability(data)
    return {name: to_records(frame) for name, frame in rank_crops(results, top_n=top_n).items()}


@app.get("/api/forecast/{crop}")
def forecast(crop: str, state: str | None = None) -> dict[str, Any]:
    database, _ = _ready()
    data = saved_annual_yields(database, crop=crop, state=state, season="Total")
    if data.empty:
        raise HTTPException(status_code=404, detail=f"No annual yield records found for {crop}")
    try:
        result = evaluate_forecasts(data, crop)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    predictions = result.get("predictions")
    if predictions is not None:
        result["predictions"] = to_records(predictions)
    return result


@app.get("/api/anomalies")
def anomalies(state: str | None = None, minimum_observations: int = 10) -> dict[str, Any]:
    database, _ = _ready()
    data = saved_annual_yields(database, state=state, season="Total")
    result = detect_yield_anomalies(data, minimum_observations=minimum_observations)
    return {"count": int(result["Anomaly"].sum()) if not result.empty else 0, "records": to_records(result)}


@app.post("/api/ingest")
async def ingest(
    file: UploadFile = File(...),
    season: str = Form("Total"),
    yield_unit: str = Form("Kg/Ha"),
) -> dict[str, Any]:
    suffix = Path(file.filename or "").suffix.casefold()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=415, detail="Upload a CSV or XLSX file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Upload exceeds the 25 MB limit")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        adapted = adapt_yield_data(load_table(temporary_path), yield_unit=yield_unit)
        data = adapted.data
        if "Season" in data and season.casefold() != "all":
            available = data["Season"].dropna().astype(str).str.strip().str.casefold()
            if not available.eq(season.casefold()).any():
                raise ValueError(f"Season {season!r} is unavailable; choose one of: {', '.join(sorted(available.unique()))}, all")
            data = select_season(data, season)
        database, _ = _ready()
        saved = database.ingest_yields(
            data,
            source_name=file.filename or "uploaded-dataset",
            source_path=f"upload:{file.filename or 'unnamed'}",
            source_type="upload",
            reporting_status="user-uploaded; not independently verified",
            default_unit=yield_unit,
        )
        return {**saved, "detected_layout": adapted.detected_layout, "issues": list(adapted.issues), "season_filter": season}
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)