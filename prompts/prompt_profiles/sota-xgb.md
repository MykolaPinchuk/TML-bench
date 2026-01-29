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
