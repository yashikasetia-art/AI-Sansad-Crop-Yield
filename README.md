# Cropwise AI

Cropwise AI is an offline-first crop-yield analysis prototype for the CALYX team. It compares crop yields over time, quantifies observed variability and downside deviations, and evaluates simple forecasting models against a previous-year baseline.

## Start on Windows

Requirements: Windows 10/11 and Python 3.11.

1. Run `setup.bat` from this folder. It creates `.venv`, installs `requirements.txt`, copies `.env.example` to `.env` if needed, audits the local datasets, and runs pytest.
2. Run `run.bat`. The dashboard opens at `http://localhost:8501`; FastAPI documentation is at `http://127.0.0.1:8000/docs`.

The system works without UPAg credentials or internet access after dependencies are installed. The historical CSV is stored in SQLite on first application use. The original source files are not modified.

## What Is Implemented

- Dataset audit for CSV/XLSX files, including the metadata and two-row header in the supplied XLSX workbook.
- Schema adapter for wide and long yield tables, with explicit column mapping support.
- Annual analysis based on source `Total` observations; it never adds Kharif, Rabi, or Summer rows together.
- Descriptive statistics, sample CV, linear detrending, empirical-cohort classes, downside deviations, and crop rankings.
- Chronological Random Forest and Gradient Boosting comparisons against a previous-year baseline, plus Isolation Forest anomaly screening and K-Means profiles.
- SQLite persistence, FastAPI routes, Streamlit analysis views, CSV/Excel/PDF exports, and optional documented UPAg authentication.

## Run Individually

```powershell
\.venv\Scripts\python.exe audit_data.py
\.venv\Scripts\python.exe -m pytest -q
\.venv\Scripts\python.exe -m uvicorn cropwise.api:app --host 127.0.0.1 --port 8000
\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

The API seeds `data/cropwise.sqlite3` from the national year-wise CSV if the database has no yield records. Override the database location with `DATABASE_PATH` or `CROPWISE_DB_PATH`.

## Data Sources and Scope

- `All-India_-Year-wise-Crop-Area,-Production-&-Yield.csv` is the primary long-term source (1966–67 through 2025–26, as listed in the source). The workbook identifies DA&FW and yield in Kg/Ha; the CSV itself does not contain a reporting-status field.
- The state-wise profile is a recent, incomplete panel. Missing cells remain missing, and 2025–26 reporting status is not independently verified.
- The district file is a 2024–25 cross-section, not a district time series.
- The progressive Rabi report describes area sown, not yield.
- The duplicated long state-wise CSV is identified in `DATA_AUDIT_REPORT.md`; ingest one copy only.

## Method Notes

CV is sample standard deviation divided by mean yield. Detrended CV uses the sample standard deviation of OLS linear-trend residuals divided by mean observed yield, so the denominator remains interpretable in yield units. Volatility classes use configurable empirical quantiles and are not official categories. The default 15% early/late residual-dispersion change is a configurable screening rule, not a validated agronomic threshold.

Forecast evaluation is chronological: early observations train the model, the next segment selects among the models and the baseline, and the final segment is held out. Features use lagged yields only. Model scores must be interpreted crop by crop and compared with the baseline; no causal claims are made.

## UPAg Configuration

Copy `.env.example` to `.env` and set `UPAG_USER`, `UPAG_PASSWORD`, and, if required by the approved deployment, `UPAG_BASE_URL`. Credentials are never committed. Without valid credentials, local dataset mode remains functional. See `API_DOCUMENTATION.md` for current implementation boundaries.

## Project Documents

See `ABSTRACT.md`, `METHODOLOGY.md`, `SYSTEM_ARCHITECTURE.md`, `DATA_AUDIT_REPORT.md`, `MODEL_EVALUATION_REPORT.md`, `LIMITATIONS_AND_FUTURE_SCOPE.md`, `DEMO_SCRIPT.md`, and the competition preparation documents in this folder.