# Model Evaluation Report

## Evaluation Design

The forecasting target is one crop's next observed annual yield, estimated with lag-1 yield, lag-2 yield, the mean of prior three observations, and a time index. Inputs are ordered chronologically. The earliest segment trains the models, the next segment selects the model by validation MAE, and the final segment is held out. Metrics are compared with the previous-year-yield baseline. This is rolling one-step evaluation: the observed yield from the immediately preceding year is available for each next-step prediction.

Random Forest and Gradient Boosting report MAE, RMSE, R-squared, training time, inference time, validation MAE, and training-only TimeSeriesSplit MAE when the training window is large enough. A model artifact is selected only using validation performance. The held-out test is not used to select the saved model.

## Verified Rice Result

Final run using `evaluate_models.py --crop Rice` on the supplied annual `Total` series:

- 60 observed years; 58 rows after lag feature construction.
- Chronological split: 34 train, 12 validation, 12 final test observations.
- Validation-selected model: previous-year-yield baseline.
- Previous-year baseline: MAE 48.917 Kg/Ha, RMSE 57.513 Kg/Ha, R-squared 0.9026.
- Random Forest: MAE 303.103 Kg/Ha, RMSE 354.726 Kg/Ha, R-squared -2.7053.
- Gradient Boosting: MAE 320.989 Kg/Ha, RMSE 370.126 Kg/Ha, R-squared -3.0340.

For this crop and split, neither tree model improved on persistence. This is a genuine measured result for the specified data and evaluation design, not a generalized accuracy claim for other crops or periods.

## Interpretation

A strong baseline result is meaningful: annual yields can be persistent, and more complex models can overfit or fail to generalize. Present metrics crop by crop with the exact source period, split sizes, observation count, and baseline. Do not select a model by its test score. Feature importance describes predictive reliance, not a causal agricultural factor.

## Runtime and Artifact Notes

The model artifact is saved only when a trained model wins on validation; the baseline is not serialized as a tree estimator. Regression tests cover the model-selected artifact path and the baseline-selected Rice case is presented as the winner. Test results are summarized in `TESTING_REPORT.md`.
