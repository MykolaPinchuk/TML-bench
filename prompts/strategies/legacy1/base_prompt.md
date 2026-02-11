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
6) Stay within this workspace. Do not read or write outside the workspace directory.
7) **Do not paste or dump CSV file contents into the chat/context window** (including `sample_submission.csv`). Treat CSVs as data files, not prompt context.

## Context hygiene (avoid blowing up the context window)

- Never “read a CSV into chat context” or paste whole files. This will fill up the context window and break the agent.


## Output and reporting

- Print a local validation score (split your `train_public.csv`).

## Workflow (recommended)

1) Create (or edit) a single script `train_model.py` that:
   - reads the `public/` CSVs,
   - trains a model,
   - prints a local validation score,
   - writes `submission.csv` that matches `public/sample_submission.csv`.
2) Run `python train_model.py` early to ensure you can generate a valid `submission.csv`.
3) Spend the remaining budget doing 1–3 fast iterations to improve local validation (model choice, hyperparameters, encoding, simple feature engineering).
4) Keep the best approach and leave a final `submission.csv` in the workspace root.

