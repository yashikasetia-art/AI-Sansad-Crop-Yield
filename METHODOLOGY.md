# Methodology

## Ingestion and Validation

CSV and XLSX files are loaded without modifying source files. The XLSX parser finds the Year/Season header beneath workbook metadata, flattens the two-level crop/measure columns, forward-fills merged year labels, and excludes blank analysis rows. The dataset adapter accepts wide crop-yield columns and long crop/year/yield columns, with optional explicit column mappings. Non-numeric and missing yields are excluded from calculations and reported as issues; negative yields are treated as invalid. Zero yields are retained unless a dataset-specific review changes that policy.

## Annual and Seasonal Series

For national annual comparisons, the data adapter selects source rows labeled `Total`. It does not sum seasonal rows or create totals. Seasonal comparisons use only named seasons. Aggregate crop labels such as Total Pulses and Total Food Grains are removed from crop-level rankings. Crop labels are preserved rather than merged on fuzzy similarity.

## Descriptive Metrics

For observed yields $y_1,\ldots,y_n$, the system reports arithmetic mean, median, minimum, maximum, range, sample variance and sample standard deviation. Sample CV is $100s_y/\bar{y}$ when at least two observations exist and the mean is positive. Consecutive changes are calculated only for consecutive available records; a zero previous yield produces a missing percentage change rather than division by zero.

## Trend and Detrended Variability

The selected detrending method is ordinary least-squares linear regression of yield on the numeric crop-year start. The fitted value is the long-run linear trend and the residual is observed yield minus fitted yield. Detrended CV is $100s_r/\bar{y}$, where $s_r$ is the sample standard deviation of residuals and $\bar{y}$ is mean observed yield. The denominator is not the residual mean because residuals are centered around zero. Linear detrending is chosen for interpretability and reproducibility; it does not represent every structural break or nonlinear agronomic response.

## Downside and Changing Volatility

Negative residual count, mean negative residual, worst negative residual, and downside deviation are reported. Downside deviation is $\sqrt{n^{-1}\sum_{t=1}^n\min(r_t,0)^2}$ and includes zero contributions for non-negative residual years. Unusually poor years use a crop-specific screen below minus two residual standard deviations; this is a screening convention, not a causal diagnosis.

The early/late volatility screen compares sample residual standard deviations in the first and second chronological halves. A relative shift above the configurable default of 15% is labeled increasing volatility; a shift below -15% is labeled improving stability. At least two records per half are required. The threshold is configurable and should be stress-tested before policy use.

## Classification and Rankings

The eligible cohort uses empirical 33rd and 67th percentiles of detrended CV by default. Lower values are labeled Stable Yield, middle values Moderate Variability, and upper values High Variability, unless the early/late screen flags increasing volatility or improving stability. These are cohort-relative analytical labels, not official government classifications. Rankings require the minimum observation count and comparable yield units.

## Machine Learning

The forecasting task is one-step-ahead yield estimation from two lagged yields, a trailing mean of prior observations, and a time index. Inputs are ordered chronologically. The earliest segment trains, a subsequent validation segment selects the reported model/artifact, and the final segment is held out. The default split yields approximately 60/20/20. Random Forest and Gradient Boosting are compared with the previous-year value baseline using MAE, RMSE, and R-squared. A model is not preferred merely because it is more complex. TimeSeriesSplit is applied within the training segment when sufficient rows are available.

Isolation Forest is applied to linear-trend residuals per crop and reports a score plus explanation text. K-Means standardizes the descriptive stability features and is only used when there are more crop profiles than requested clusters. Neither model supplies causal explanations.

## Limitations

Observation availability varies by crop and historical period. Source revisions, changes in measurement/reporting, structural breaks, and estimate status are not harmonized. State panel missingness is extensive. A high or low historical CV is not itself a forecast or a measure of farmer welfare. See `LIMITATIONS_AND_FUTURE_SCOPE.md`.