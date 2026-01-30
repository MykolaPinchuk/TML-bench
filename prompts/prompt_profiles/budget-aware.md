## Prompt profile: budget-aware (single policy across budgets)

Goal: follow the *same workflow policy* regardless of budget, but scale effort with the available time.

You have **{{time_budget_seconds}} seconds** total. You must be budget-aware:

### Stage plan (budget-aware; do not overrun)

1) **Stage 1 (bootstrap, must succeed):** finish a fully-valid `submission.csv` quickly.
   - Compute `stage1_seconds = min(60, max(45, int(0.2 * {{time_budget_seconds}})))`.
   - Within `stage1_seconds`, create `train_model.py`, run it, and ensure `submission.csv` is valid.
   - Use a fast baseline first (keep preprocessing simple; avoid slow models).
   - If anything breaks, revert to the last-known-valid `submission.csv` immediately (keep a backup copy).

2) **Stage 2 (iterate, scale with budget):** improve score until close to the budget.
   - Continue iterating until you reach ~90% of the budget (do not stop early just because you have a working solution).
   - Only attempt heavier approaches (more features, stronger models like gradient boosting) if you have enough time remaining.
   - Prefer changes that are likely to generalize; avoid “validation hacking”.

### Reliability rules (non-negotiable)

- Always leave a valid `submission.csv` in the workspace root.
- After every meaningful change, re-run `python train_model.py` and re-validate that `submission.csv` matches the sample format.
- Keep `train_model.py` runnable and non-empty; verify with `wc -c train_model.py` and `python -m py_compile train_model.py`.
- Do not install packages.

