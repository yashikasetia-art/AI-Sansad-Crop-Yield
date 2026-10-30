# Round 2 Quick Execution Guide

## Before the Challenge

1. Run `setup.bat`; confirm pytest and the audit complete.
2. Run `run.bat`; confirm the dashboard and `/docs` open.
3. Keep the environment warm and the local database seeded.
4. Rehearse a run without network access.

## New Dataset Workflow

1. Upload CSV/XLSX in Data & Reports and inspect column names and the preview.
2. Map crop, year, yield, and optional season/state/district fields.
3. Confirm the yield unit and select `Total`, a named season, or `All` intentionally.
4. Review missing/non-numeric/negative-value warnings and verify there are no duplicate crop-year-scope keys.
5. Store data, query it back, and confirm the source and reporting status.
6. Run variability analysis only when periods and units are comparable.
7. Train/evaluate a model only when the series is long enough; always compare with the previous-year baseline.
8. Export results with source, period, sample count, and limitations.

## Fast Commands

```powershell
.\.venv\Scripts\python.exe audit_data.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn cropwise.api:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

## Defensible Claims

- Do not silently fill missing yields with zero.
- Do not mix area/production measures with yield.
- Do not select a model using its final test segment.
- Do not infer district volatility from one year.
- If a model loses to persistence, report the baseline as preferable.
