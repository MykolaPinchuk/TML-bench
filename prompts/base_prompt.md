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

- Never “read a CSV into chat context” or paste whole files.
- If you need schema/shape, use tiny summaries only:
  - `python - <<'PY'\nimport pandas as pd\nfor p in ['public/train_public.csv','public/test_public.csv','public/sample_submission.csv']:\n  df=pd.read_csv(p, nrows=5)\n  print(p, 'cols=', list(df.columns))\nPY`
  - `head -n 5 public/sample_submission.csv`
  - `python -c "import pandas as pd; print(pd.read_csv('public/train_public.csv').shape)"`
  - Only print small outputs (header + a few rows), never full datasets.

## Output and reporting

- Print a local validation score (split your `train_public.csv`).
