# Demo Script (5 Minutes)

## 0:00–0:35 | Problem
“Cropwise AI answers the assigned question: which crop yields are relatively stable, which fluctuate, and whether volatility is changing. We focus on yield in Kg/Ha, not production or cultivated area.”

## 0:35–1:10 | Data Integrity
Show the data audit. Explain that annual national analysis selects source `Total` rows and never sums Kharif, Rabi, and Summer. Point out that the state file is incomplete and the district file is one-year only. Missing observations stay missing.

## 1:10–2:10 | Statistics
Open Variability. Explain sample CV and detrended CV, including mean yield as the residual-SD denominator. Show observation counts, period, and cohort-relative classes. State that labels are analytical, not official.

## 2:10–2:55 | Risk and geography
Show downside residual rankings and one state or district view. Clarify that the district chart is a 2024–25 cross-section, not a historical trend. Anomaly flags are screening signals, not causes.

## 2:55–4:00 | ML evidence
Open AI/ML Insights for a crop with enough history. Compare Random Forest and Gradient Boosting against the previous-year baseline. Lead with measured holdout results and split design. If neither model beats the baseline, say so plainly.

## 4:00–4:35 | Architecture
Show SQLite-backed retrieval, FastAPI `/docs`, and the local fallback. Mention that UPAg credentials are optional and no live API output is simulated.

## 4:35–5:00 | Close
“Cropwise makes every comparison traceable to a source, period, and observation count. The next step is broader rolling-origin evaluation and richer validated explanatory data, not stronger claims than the evidence supports.”

## Demo Safety Checks

- Run `setup.bat` and `run.bat` before presenting.
- Confirm both local URLs work and the database contains annual records.
- Avoid describing a recent estimate as final unless its reporting status is verified.
- Use screenshots or the offline dataset if venue internet is unavailable.
