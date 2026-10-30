"""SQLite persistence with idempotent dataset ingestion."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "cropwise.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class CropwiseDatabase:
    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _ensure_dimension(self, connection: sqlite3.Connection, table: str, name: str) -> int:
        connection.execute(f"INSERT INTO {table}(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (name,))
        row = connection.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
        return int(row["id"])

    def ingest_yields(
        self,
        data: pd.DataFrame,
        *,
        source_name: str,
        source_path: str | None = None,
        source_type: str = "local",
        reporting_status: str = "unverified",
        default_unit: str = "unknown",
    ) -> dict[str, int]:
        required = {"Crop", "Year", "Yield"}
        if not required.issubset(data.columns):
            raise ValueError(f"Required columns: {', '.join(sorted(required))}")
        clean = data.dropna(subset=["Crop", "Year", "Yield"]).copy()
        clean["Yield"] = pd.to_numeric(clean["Yield"], errors="coerce")
        clean = clean.dropna(subset=["Yield"])
        if (clean["Yield"] < 0).any():
            raise ValueError("Negative yields must be resolved before database ingestion")

        content = clean.to_csv(index=False).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        created = 0
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO data_sources(name, source_path, sha256, source_type,
                   reporting_status, last_successful_update) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name, sha256) DO UPDATE SET
                   last_successful_update=excluded.last_successful_update""",
                (source_name, source_path, digest, source_type, reporting_status, datetime.now(timezone.utc).isoformat()),
            )
            source = connection.execute("SELECT id FROM data_sources WHERE name=? AND sha256=?", (source_name, digest)).fetchone()
            source_id = int(source["id"])
            for record in clean.to_dict(orient="records"):
                crop_name = str(record["Crop"]).strip()
                year = str(record["Year"]).strip()
                state_name = str(record["State"]).strip() if pd.notna(record.get("State")) else None
                district_name = str(record["District"]).strip() if pd.notna(record.get("District")) else None
                season_name = str(record["Season"]).strip() if pd.notna(record.get("Season")) else None
                crop_id = self._ensure_dimension(connection, "crops", crop_name)
                state_id = self._ensure_dimension(connection, "states", state_name) if state_name else None
                district_id = None
                if district_name:
                    if not state_id:
                        raise ValueError("District records require a state")
                    connection.execute("INSERT INTO districts(state_id, name) VALUES (?, ?) ON CONFLICT(state_id, name) DO NOTHING", (state_id, district_name))
                    district_id = int(connection.execute("SELECT id FROM districts WHERE state_id=? AND name=?", (state_id, district_name)).fetchone()["id"])
                season_id = self._ensure_dimension(connection, "seasons", season_name) if season_name else None
                unit = str(record.get("YieldUnit") or default_unit)
                key = "|".join((crop_name.casefold(), state_name.casefold() if state_name else "", district_name.casefold() if district_name else "", season_name.casefold() if season_name else "", year, str(source_id)))
                cursor = connection.execute(
                    """INSERT INTO yield_records(record_key, crop_id, state_id, district_id,
                       season_id, crop_year, value, unit, source_id, reporting_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(record_key) DO NOTHING""",
                    (key, crop_id, state_id, district_id, season_id, year, float(record["Yield"]), unit, source_id, reporting_status),
                )
                created += cursor.rowcount
        return {"inserted": created, "rows_seen": len(clean), "source_id": source_id}

    def get_yields(
        self,
        *,
        crop: str | None = None,
        state: str | None = None,
        season: str | None = None,
    ) -> pd.DataFrame:
        query = """SELECT c.name AS Crop, s.name AS State, se.name AS Season,
                   y.crop_year AS Year, y.value AS Yield, y.unit AS YieldUnit,
                   ds.name AS Source, y.reporting_status AS ReportingStatus
                   FROM yield_records y JOIN crops c ON c.id=y.crop_id
                   LEFT JOIN states s ON s.id=y.state_id
                   LEFT JOIN seasons se ON se.id=y.season_id
                   JOIN data_sources ds ON ds.id=y.source_id WHERE 1=1"""
        parameters: list[Any] = []
        for column, value in (("c.name", crop), ("s.name", state), ("se.name", season)):
            if value:
                query += f" AND {column} = ?"
                parameters.append(value)
        query += " ORDER BY y.crop_year, c.name"
        with self.connect() as connection:
            return pd.read_sql_query(query, connection, params=parameters)

    def save_variability(self, results: pd.DataFrame, source_name: str) -> int:
        inserted = 0
        with self.connect() as connection:
            source = connection.execute("SELECT id FROM data_sources WHERE name=? ORDER BY id DESC LIMIT 1", (source_name,)).fetchone()
            if source is None:
                raise ValueError(f"Unknown data source {source_name!r}")
            source_id = int(source["id"])
            for record in results.to_dict(orient="records"):
                crop_id = self._ensure_dimension(connection, "crops", str(record["Crop"]))
                state_id = self._ensure_dimension(connection, "states", str(record["State"])) if pd.notna(record.get("State")) else None
                season_id = self._ensure_dimension(connection, "seasons", str(record["Season"])) if pd.notna(record.get("Season")) else None
                payload = json.dumps(record, default=str)
                cursor = connection.execute(
                    """INSERT INTO variability_results(crop_id, state_id, season_id, source_id, result_json)
                       VALUES (?, ?, ?, ?, ?) ON CONFLICT(crop_id, state_id, season_id, source_id)
                       DO UPDATE SET result_json=excluded.result_json, created_at=CURRENT_TIMESTAMP""",
                    (crop_id, state_id, season_id, source_id, payload),
                )
                inserted += max(cursor.rowcount, 0)
        return inserted

    def counts(self) -> dict[str, int]:
        tables = ("crops", "states", "districts", "seasons", "data_sources", "yield_records", "production_records", "area_records", "model_runs", "variability_results", "anomaly_records", "api_logs")
        with self.connect() as connection:
            return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def log_api(self, endpoint: str, method: str, status_code: int | None, outcome: str, message: str = "") -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO api_logs(endpoint, method, status_code, outcome, message) VALUES (?, ?, ?, ?, ?)", (endpoint, method, status_code, outcome, message[:500]))