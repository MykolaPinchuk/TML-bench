## Prompt profile: sota-xgb (20 min)

Goal: maximize score under a long budget, using a thorough iterative workflow.

Time management: within the first ~3 minutes, ensure you can generate a valid `submission.csv` end-to-end (create `train_model.py` and run `python train_model.py`), then spend the rest improving.

Execution note: use shell commands to write files and verify `train_model.py` / `submission.csv` exist (avoid IDE/editor tools).

XGBoost (`xgboost`) is available and allowed for this run (you may use it if you choose).

Use the time budget aggressively:
- Train an initial strong model, then keep improving it.
- If time remains, do comprehensive EDA + model diagnostics, identify failure modes, and iterate on fixes.
- You may generate intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.

Always leave a valid `submission.csv` behind.

Do not install packages.
Use any remaining time for comprehensive EDA + diagnostics to identify failure modes and iterate on fixes.

## Remaining-time reasoning gate (6 min, 150 sec)

At the very start, record the start time:
- `START_TS=$(date +%s)`
- `BUDGET={{time_budget_seconds}}`
- `time_remaining() { echo $((BUDGET - ($(date +%s) - START_TS))); }`

If (and only if) you already have a valid `submission.csv` **and** you estimate `time_remaining >= 360s`:

1) Spend up to **150 seconds** on structured reasoning (do not exceed):
   - Base it only on `public/README_task.md` and quick EDA you run (no external knowledge).
   - Think about target/metric implications and 2–4 concrete improvements (features, validation, model tweaks).

2) After reasoning, immediately execute the plan (run commands).

Safety:
- Never break your last-known-valid `submission.csv`. If you experiment, keep a backup copy and restore if needed.
