## Prompt profile: sota-xgb (20 min)

Goal: maximize score under a long budget, using a thorough iterative workflow.

Run `python train_model.py` early to validate the full pipeline end-to-end.

XGBoost (`xgboost`) is available and allowed for this run (you may use it if you choose).

Use the time budget aggressively:
- Train an initial strong model, then keep improving it.
- If time remains, do comprehensive EDA + model diagnostics, identify failure modes, and iterate on fixes.
- You may generate intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.

Always leave a valid `submission.csv` behind.

Do not install packages.
