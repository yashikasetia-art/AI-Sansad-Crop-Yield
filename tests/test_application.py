import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from cropwise import api
from cropwise.ml import evaluate_forecasts
from database.db import CropwiseDatabase


def test_forecast_uses_configured_chronological_test_fraction_and_saves_artifact(tmp_path):
    years = np.arange(1980, 2025)
    yields = np.where(years % 2, 1000.0, 100.0) + 2 * np.sin(years)
    data = pd.DataFrame({"Crop": "Rice", "Year": years.astype(str), "Yield": yields})

    result = evaluate_forecasts(data, "Rice", test_fraction=0.25, artifact_dir=tmp_path)

    expected_test_count = result["feature_observations"] - int(result["feature_observations"] * 0.75)
    assert result["status"] == "evaluated"
    assert result["test_count"] == len(result["predictions"]) == expected_test_count
    assert result["model_path"] is not None
    assert (tmp_path / result["model_path"].split("\\")[-1]).exists()


def test_api_reads_persisted_yield_and_variability_records(tmp_path, monkeypatch):
    database = CropwiseDatabase(tmp_path / "test.sqlite3")
    database.initialize()
    source = pd.DataFrame({
        "Crop": ["Rice"] * 6,
        "Year": [str(year) for year in range(2018, 2024)],
        "Season": ["Total"] * 6,
        "Yield": [3000, 3100, 3050, 3200, 3180, 3300],
        "YieldUnit": ["Kg/Ha"] * 6,
    })
    database.ingest_yields(source, source_name="test.csv", default_unit="Kg/Ha")
    monkeypatch.setattr(api, "_database", lambda: database)

    yield_response = api.yields(crop="Rice")
    variability_response = api.variability()
    empty_rankings = api.rankings(season="Kharif")

    assert yield_response["count"] == 6
    assert yield_response["records"][0]["Yield"] == 3000
    assert variability_response["count"] == 1
    assert variability_response["records"][0]["ObservationCount"] == 6
    assert all(not records for records in empty_rankings.values())

    with TestClient(api.app) as client:
        response = client.get("/api/yields", params={"crop": "Rice"})
        assert response.status_code == 200
        assert response.json()["count"] == 6

        upload = client.post(
            "/api/ingest",
            files={"file": ("wheat.csv", b"Crop,Year,Season,Yield\nWheat,2022-23,Total,3200\nWheat,2023-24,Total,3300\n", "text/csv")},
            data={"season": "Total", "yield_unit": "Kg/Ha"},
        )
        assert upload.status_code == 200
        assert upload.json()["inserted"] == 2
        assert len(database.get_yields(crop="Wheat")) == 2