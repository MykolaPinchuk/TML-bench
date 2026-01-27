## Prompt profile: good-baseline

Goal: use most of the budget to iteratively improve the local validation score.

Run `python train_model.py` early to validate the full pipeline end-to-end.

Do not stop after the first working solution. Keep iterating until you are close to the time budget:
- Try multiple approaches and compare them using a consistent local validation setup.
- Do basic analysis to understand why errors happen and what changes help.
- You may generate intermediate submissions, but you must leave the best one as `submission.csv` in the workspace root.

Always leave a valid `submission.csv` behind.

Do not install packages.
