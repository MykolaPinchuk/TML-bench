# Playground Series S5E10 — Road Accident Risk Prediction

## Goal
Train a regression model on `train_public.csv` to predict `accident_risk`.

## Files
- `train_public.csv`: features + `accident_risk` (label)
- `test_public.csv`: features only (no label)
- `sample_submission.csv`: required submission schema

## Output
Write `submission.csv` in the current working directory:
- columns must match `sample_submission.csv` exactly
- row count and IDs must match `test_public.csv`

## Constraints (benchmark policy)
- Do not use web browsing or external data sources.
- Keep everything reproducible within the run budget.

