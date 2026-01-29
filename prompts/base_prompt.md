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

## Execution environment note (headless)

- Prefer shell commands for inspection and file I/O (`ls`, `cat`, `head`, `python ...`).
- Do NOT use editor/IDE-specific tools (e.g. `readFile`, `writeFile`, `newFileCreated`, `updateTodoList`). Assume they may silently fail or create empty files.
- Create/edit files using shell redirection or heredocs (example pattern): `cat > train_model.py <<'PY' ... PY`.

## Output discipline (important)

- Keep chat output short. Avoid long reasoning, long plans, or large code blocks.
- Do **not** write the full `train_model.py` code in the chat. Write it to a file via shell redirection/heredocs.
- Do **not** create or update “todo lists” in the chat. If you must plan, use ≤5 short bullets and then execute immediately.
- If you are about to produce a long response, stop and run the next shell command instead.

## Output and reporting

- Print a local validation score (split your `train_public.csv`).

## Workflow (recommended)

1) Create (or edit) a single script `train_model.py` that:
   - reads the `public/` CSVs,
   - trains a model,
   - prints a local validation score,
   - writes `submission.csv` that matches `public/sample_submission.csv`.
2) After writing `train_model.py`, verify it is non-empty and runnable (e.g. `wc -c train_model.py` and `python -m py_compile train_model.py`).
3) Run `python train_model.py` early to ensure you can generate a valid `submission.csv`.
4) Verify `submission.csv` exists and matches the required format (same columns + row count as the sample).
5) Use the remaining time budget to improve your local validation score via iteration.
   - You may try multiple approaches and re-run training multiple times.
   - You may write intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.
6) Prefer not to stop early; keep improving until you are close to the time budget and confident the current `submission.csv` is your best attempt.
