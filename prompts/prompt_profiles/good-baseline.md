## Prompt profile: good-baseline

Goal: use most of the budget to iteratively improve the local validation score.

Time management: ensure you have a working end-to-end pipeline early (within the first ~2 minutes, create `train_model.py` and run `python train_model.py`), then spend most of the remaining budget iterating and improving.

Execution note: use shell commands to write files and verify `train_model.py` / `submission.csv` exist (avoid IDE/editor tools).

Do not stop after the first working solution. Keep iterating until you are close to the time budget:
- Try multiple approaches and compare them using a consistent local validation setup.
- Do basic analysis to understand why errors happen and what changes help.
- You may generate intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.

Always leave a valid `submission.csv` behind.

Do not install packages.
Use any remaining time for lightweight EDA/diagnostics to decide what to try next.

## Remaining-time reasoning gate (6 min, 150 sec)

At the very start, record the start time:
- `START_TS=$(date +%s)`
- `BUDGET={{time_budget_seconds}}`
- `time_remaining() { echo $((BUDGET - ($(date +%s) - START_TS))); }`

If (and only if) you already have a valid `submission.csv` **and** you estimate `time_remaining >= 360s`:

1) Spend up to **150 seconds** on structured reasoning (do not exceed):
   - Base it only on `public/README_task.md` and quick EDA you run (no external knowledge).
   - Think about the target, metric, feature types, leakage risks, and 2–4 concrete improvements to try next.

2) After reasoning, immediately execute the plan (run commands).

Safety:
- Never break your last-known-valid `submission.csv`. If you experiment, keep a backup copy and restore if needed.
