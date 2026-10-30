# API Documentation

FastAPI OpenAPI UI is available at `/docs` after launching `uvicorn cropwise.api:app`.

## Local Application Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/status` | Initialize/check local database, record counts, source and credential-configuration status |
| GET | `/api/yields` | Query saved records; optional `crop`, `state`, and `season` (default `Total`, `all` disables season filter) |
| GET | `/api/variability` | Compute variability; optional `state`, `season`, and `minimum_observations` |
| GET | `/api/rankings` | Return stable, variable, increasing-volatility, declining-yield, and downside rankings; `top_n` 1–100 |
| GET | `/api/forecast/{crop}` | Chronological model and previous-year-baseline evaluation for a saved crop series |
| GET | `/api/anomalies` | Isolation Forest residual screen for saved annual yields |
| POST | `/api/ingest` | Upload CSV/XLSX multipart form with `file`, `season`, and `yield_unit` |

Errors use standard HTTP status codes. Invalid uploads and parameters return 4xx responses; unexpected server errors are not disguised as successful data.

## Upload Contract

Accepted file types are CSV and XLSX, limited to 25 MB. The adapter detects common long and wide layouts or rejects data where it cannot identify yield/year fields. `season` defaults to `Total`; specify a named season or `all` where appropriate. Records carry user-uploaded provenance and an unverified reporting status. Missing values are not replaced with zero. Duplicate ingestion is idempotent for a source digest and observation key.

## UPAg Data Share Integration

`api_integration/upag_client.py` implements the published Data Share pattern: POST username/password to `/v1/upag/api-data-share/login`, retain the bearer token, query allowed sources, and POST source inputs with `limit` and `offset`. It validates expected response shapes and retries limited transient errors. The API documentation describes userid/password authentication; this project does not ship credentials.

The client also exposes documented APY filter, crop-master, crop-production, statewise-APY, and districtwise-APY methods. Endpoint payload schemas vary; check the current OpenAPI spec and approved user source definitions before requesting live data. No rate limit is assumed where none is documented.

## Configuration

Set `UPAG_BASE_URL`, `UPAG_USER`, `UPAG_PASSWORD`, and optionally `DATABASE_PATH` in `.env`. Never commit `.env`. When credentials are absent, live access is reported as unavailable and local mode remains active.