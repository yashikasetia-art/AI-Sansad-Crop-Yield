# Limitations and Future Scope

## Current Limitations

- The national source is observational and does not include weather, soil, irrigation, variety, input, or policy covariates. It supports description and conditional forecasting, not causal attribution.
- Historical definitions, source revisions, reporting quality, and structural breaks are not harmonized in the supplied files.
- Mean-based CV is undefined or unstable for non-positive means; such groups are not meaningfully ranked by CV.
- Linear detrending can miss nonlinear trends and structural breaks. The current model is intentionally simple and should be stress-tested against robust alternatives before deployment.
- Empirical quantile classes depend on the comparison cohort and are not official categories. The 15% volatility-shift rule and two-standard-deviation poor-year screen are configurable screening rules, not agronomic standards.
- State panel data span only recent crop years and have extensive missingness. District data contain one year only. Neither supports historical geographic volatility claims.
- Some source zero yields may represent real observations, placeholders, or reporting artifacts; they are retained and require source-specific interpretation.
- UPAg credentials and approved source entitlements are not provided. The authenticated connector is therefore not verified against a live account.
- SQLite is implemented. PostgreSQL compatibility is not certified, and area/production, model-run, variability-result, and anomaly-record persistence is not yet fully integrated into workflows.
- Dashboard upload is functional for common layouts, but complex new data schemas may need explicit column mapping and manual unit validation.

## Future Scope

1. Validate annual source revisions and add formal versioned source metadata.
2. Compare OLS detrending with robust regression and break-aware methods using pre-registered selection criteria.
3. Evaluate forecast models with multiple rolling-origin folds and multiple crops, then publish per-crop baselines and uncertainty intervals.
4. Add weather, irrigation, and soil covariates only with a documented causal/predictive design and provenance.
5. Add state and district records to persistent storage with explicit geographic dimensions and source-specific missingness reporting.
6. Complete UPAg extraction using approved credentials and source input schemas, retaining request logs and response hashes.
7. Add migration tooling and certify PostgreSQL only when deployment requires it.
8. Browser-test dashboard filters, accessible navigation, exports, and upload failure states.
