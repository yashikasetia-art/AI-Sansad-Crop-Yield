# Data Dictionary

## Normalized Yield Record

| Field | Meaning | Handling |
|---|---|---|
| `Crop` | Source crop label | Trim whitespace; no fuzzy merging |
| `Year` | Crop-year label, e.g. 2024-25 | Kept as source text; parsed to start year only for ordering/trend |
| `Yield` | Observed yield | Numeric; missing/non-numeric excluded from calculation; negative treated as invalid |
| `YieldUnit` | Measurement unit | Source/workbook indicates Kg/Ha; unknown remains explicitly unknown |
| `Season` | Kharif, Rabi, Summer, Total, or source label | Annual national analysis selects `Total`; no season summation |
| `State` | State/UT source name | Optional; state panel is short and incomplete |
| `District` | District source name | Optional; district file is one-year snapshot |
| `Source` | Dataset identity | Stored and exposed for provenance |
| `ReportingStatus` | Known or unknown publication status | No status is inferred from missingness; user uploads are marked unverified |

## Analysis Fields

`MeanYield`, `MedianYield`, `MinimumYield`, `MaximumYield`, `StandardDeviation`, `Variance`, and `Range` describe observed values. `CVPercent` is sample standard deviation divided by mean yield, multiplied by 100. `DetrendedCVPercent` is sample standard deviation of OLS linear-trend residuals divided by mean observed yield, multiplied by 100. `TrendSlopePerYear` is the fitted yield change per crop-year start. `NegativeDeviationYears`, `AverageNegativeDeviation`, `WorstNegativeDeviation`, and `DownsideDeviation` quantify below-trend deviations. `UnusuallyPoorYears` uses a residual threshold of -2 residual standard deviations. `ObservationCount`, `StartYear`, and `EndYear` define the evidence window.

`VolatilityDirection` compares residual standard deviation in the two chronological halves using the configurable default threshold. `StabilityClass` applies empirical detrended-CV quantiles unless a directional volatility label applies. It is not an official classification.

## Source-specific Caveats

- The annual national CSV includes seasonal rows and annual `Total` rows. Filter before calculating.
- State-year values contain extensive missingness, including the latest year; null is not zero.
- Yield zeroes occur in the historical series for some early maize/ragi observations and are retained for audit/context, though their substantive interpretation should be reviewed.
- District yield zeroes exist in the 2024–25 cross-section. They are not automatically discarded.
- Progressive Rabi rows contain area-sown measures and must not enter the yield analysis table.
