# AI Sansad Technical Debate Handbook

## Opening Statement (60–90 Seconds)

“Honourable Chair and fellow delegates, our assigned question is how crop yields compare across years and which crops experience greater variability. CALYX built Cropwise AI around a simple principle: measure yield directly, preserve the source’s annual and seasonal distinctions, and make uncertainty visible. Our national annual analysis uses the reported `Total` records rather than adding Kharif, Rabi, and Summer. We report sample coefficient of variation alongside a linear detrended measure, observation counts, trends, and negative deviations. For forecasting, we compare Random Forest and Gradient Boosting with a previous-year baseline using chronological splits. In our exploratory Rice evaluation, the baseline substantially outperformed both tree models, so we do not claim machine learning is automatically superior. The system works offline, stores provenance in SQLite, and offers a dashboard for researchers and policymakers. Our result is not a causal explanation of yield changes; it is a reproducible starting point for transparent discussion and better-targeted data collection.”

## Technical Defence: Concise Answers

1. **Why this approach?** It separates data validation, descriptive statistics, model evaluation, and presentation, so claims can be traced to observations and assumptions.
2. **Why yield rather than production?** The assigned question concerns output per unit area. Production also changes with cultivated area, so it cannot substitute for yield.
3. **Why CV?** It scales standard deviation by mean yield, enabling relative dispersion comparisons when means are positive and units are comparable.
4. **Why detrend?** A rising long-run level can inflate raw spread; residual dispersion asks how variable yields are around a simple fitted trend. It is complementary to, not a replacement for, raw CV.
5. **Why linear regression detrending?** It is interpretable and reproducible. It can miss nonlinear trends and breaks, which we state as limitations.
6. **Why Random Forest?** It tests a nonlinear lag-based estimator without a parametric linear response assumption. It is an experiment, not a guaranteed winner.
7. **Why Gradient Boosting?** It offers a second tree-based benchmark with a different additive fitting strategy; both are tested against persistence.
8. **Why clustering?** It can summarize descriptive profiles for exploration. Cluster labels are not natural crop classes and depend on chosen features/scaling.
9. **Why anomaly detection?** Isolation Forest can screen unusual residuals when labels are unavailable. A flag is not an explanation of the cause.
10. **How are missing values handled?** Missing yields remain missing and are excluded from calculations; they are never silently set to zero.
11. **How avoid leakage?** Features use prior yields only; chronological train/validation/test ordering prevents future observations entering earlier training.
12. **How validate forecasts?** Use a final chronological holdout, training-only time-series folds where feasible, and a previous-year-yield baseline.
13. **What if data are incomplete?** Report available observation count and period, suppress rankings/predictions below minimum data requirements, and retain missingness warnings.
14. **What are the limitations?** Source changes and structural breaks are not harmonized; causal covariates are absent; state and district time coverage is short.
15. **How know results are reliable?** Independent hand-calculated tests, edge-case tests, source hashes, provenance, explicit formulas, and validation against a simple baseline. Reliability is conditional on input quality.

## Thirty Difficult Opponent Questions

1. How do you know yield units remain consistent across six decades?
2. What happens if crop names change or one crop is split into varieties?
3. Why use a linear trend when agriculture may have structural breaks?
4. Does detrending remove climate-driven long cycles that policymakers should care about?
5. Why divide residual standard deviation by mean yield rather than trend level?
6. Is sample CV comparable for crops with very different measurement precision?
7. How do missing observations affect your volatility ranking?
8. Do you assume missing years are missing at random?
9. Why retain a reported zero yield if it may be a placeholder?
10. How do you distinguish provisional from final estimates?
11. Can national yield hide state-level risk heterogeneity?
12. Why not aggregate district data across multiple years?
13. How do you avoid double-counting aggregate crop categories?
14. Does the `Total` series have exactly the same definition in every year?
15. Why choose a two-standard-deviation downside screen?
16. Why is the early/late volatility threshold 15%?
17. How sensitive are classes to the selected crop cohort?
18. Do empirical quantile classes change when a new crop is added?
19. What is the ML task, and is it a true forecast or a retrospective fit?
20. Why use lag features without weather or input variables?
21. Does your test split account for multi-year forecast horizons?
22. Why report R-squared on a small holdout?
23. What if the baseline is stronger than both ML models?
24. How do you tune models without leaking test data?
25. Why use a Random Forest instead of a simpler autoregressive model?
26. How does Isolation Forest explain why an observation is unusual?
27. Are clusters stable across random seeds and feature choices?
28. How do you verify the UPAg response schema and API entitlements?
29. What prevents a duplicate upload from double-counting records?
30. What policy decision can your dashboard responsibly recommend today?

## Evidence-Based Rebuttal Points

- **“Statistics are too simple.”** A transparent baseline is a strength for a descriptive question. Complexity is useful only when it improves validated decisions.
- **“Machine learning is more accurate.”** Accuracy is empirical. In an exploratory Rice run, persistence beat both tested tree models. We report that result rather than hiding it.
- **“Historical data are irrelevant.”** Historical data reveal observed variation and support baseline comparisons, but shifts in definitions and future conditions limit direct extrapolation.
- **“API dependence makes this fragile.”** The demo is offline-first. UPAg is optional and clearly credential-gated; local sources remain available.
- **“Explainability is only feature importance.”** We provide formula-level statistical explanations, period/count provenance, model feature importance, and residual-based anomaly reasons. None proves causation.
- **“Your categories are arbitrary.”** They are explicitly cohort-relative quantiles with configurable thresholds, not official categories; users can inspect continuous values and sensitivity.

## Cross-Questions for Other Teams

- What is the target variable and its exact unit?
- How do you separate annual totals from seasonal records?
- What is your chronological test design and baseline?
- How are nulls and zero values distinguished?
- Can you reproduce the reported score from a fixed dataset and split?
- Are your labels official, learned, or manually chosen?
- Which claims are descriptive, predictive, or causal?
- What happens when your model loses to a naive baseline?

## Collaborative Resolution

Propose a shared evaluation protocol: source and unit registry, versioned data, explicit annual/season rules, null-preserving validation, common chronological holdout, published naive baselines, per-crop uncertainty and sample counts, interpretable anomaly flags, and a route for agronomists to review provisional results. Combine the best methods only after testing them on the same held-out observations.

## Speaking Roles

Use `TEAM_ROLE_ALLOCATION.md` for four-person assignments. For three speakers, combine data provenance with demo/policy, while keeping statistics and ML validation as separate responsibilities. All members should agree on the source period, unit, `Total` rule, and model split before the session.
