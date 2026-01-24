# Task

You are an autonomous ML agent working on a tabular Kaggle-style task.

## Inputs

You have access only to:
- `public/train_public.csv`
- `public/test_public.csv`
- `public/sample_submission.csv`
- `public/README_task.md`

## Requirements (non-negotiable)

1) Train a model on `public/train_public.csv`.
2) Write `submission.csv` in the **workspace root**.
3) `submission.csv` must match `public/sample_submission.csv` exactly:
   - same column names
   - same row count
   - same ID set (the `id` column)
4) Do not use web browsing or external data sources.
5) Keep work within the time budget: {{time_budget_seconds}} seconds.

## Output and reporting

- Print a local validation score (split your `train_public.csv`).
