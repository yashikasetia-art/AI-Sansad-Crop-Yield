# Database Schema

SQLite is the initial persistence layer. Tables use integer primary keys, foreign keys, created timestamps, and uniqueness constraints where duplicate ingestion must be prevented. Foreign-key enforcement is enabled on each connection. The schema is kept SQL-portable where practical; no PostgreSQL deployment has been certified.

## Tables

- `crops`, `states`, `seasons`: normalized dimension names.
- `districts`: district name scoped to a state, unique per state.
- `data_sources`: source path/type, content hash, reporting status, and last successful update.
- `yield_records`: crop-year yield and unit, optional geographic/season dimensions, source provenance and status; `record_key` prevents duplicate records.
- `area_records`, `production_records`: schema-ready measurement tables for future ingestion; current loader persists yield only.
- `api_logs`: endpoint, method, status, outcome and short message.
- `model_runs`: model identity, parameters, metrics and optional artifact path.
- `variability_results`: saved serialized result associated with crop/scope/source.
- `anomaly_records`: anomaly/trend values and explanation, scoped by source and crop-year.

## Indexes and Constraints

Indexes cover yield by crop/year, state/year, season, source, and district/state. Unique constraints cover crop names, state names, district within state, season names, data-source name/hash, yield record key, variability scope/source, and anomaly crop/state/year/source.

## Ingestion Notes

`CropwiseDatabase.ingest_yields` rejects negative yields, drops missing crop/year/yield rows without imputing, and builds deterministic record keys. The current service seeds from the national annual-total source and stores the original source path and a status stating that estimate status was not independently verified. State and district views currently load their supplied CSVs directly for analysis and are not seeded into the database automatically.
