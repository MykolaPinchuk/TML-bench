## Prompt profile: good-baseline

Goal: use most of the budget to iteratively improve the local validation score.

Time management: ensure you have a working end-to-end pipeline early (create `train_model.py` and run `python train_model.py`), then spend most of the remaining budget iterating and improving.

Execution note: use shell commands to write files and verify `train_model.py` / `submission.csv` exist (avoid IDE/editor tools).

Do not stop after the first working solution. Keep iterating until you are close to the time budget:
- Try multiple approaches and compare them using a consistent local validation setup.
- Do basic analysis to understand why errors happen and what changes help.
- You may generate intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.

Always leave a valid `submission.csv` behind.

Do not install packages.
Use any remaining time for lightweight EDA/diagnostics to decide what to try next.
