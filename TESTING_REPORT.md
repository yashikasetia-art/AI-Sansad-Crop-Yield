# Testing Report

## Verified

- Full pytest suite: 8 passed.
- The six adapter/statistics tests and two application regressions passed.
- Application regressions cover configurable chronological forecast splitting, validation-selected model artifact saving, and API retrieval of SQLite-backed yield and variability records.
- Dataset audit ran over all 8 supplied CSV/XLSX datasets; `DATA_AUDIT_REPORT.md` records file-level shapes, types, missing values, zero/negative counts, duplicates, categories, and file hashes.
- The presentation and four PDF files were generated from the current source data and documents.
- Streamlit dashboard started successfully and rendered the seeded local source with 1,990 stored annual observations.
- Editor diagnostics reported no issues in the added Python modules and tests.

## Known Test Gaps

FastAPI multipart upload failures, live UPAg authentication, and all dashboard controls have not been exhaustively browser-tested. Live API behavior requires valid approved credentials. These are not reported as passing.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run `setup.bat` to provision the project environment on a machine where package installation is available.
