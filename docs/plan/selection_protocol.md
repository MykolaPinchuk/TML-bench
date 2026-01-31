# Plan: Candidate submissions + selection-vs-evaluation protocol

This document describes a diagnostic protocol to answer:

1) Do agents generate better solutions with more time (**search/modeling**)?
2) If yes, do agents correctly identify which candidate is best (**selection**)?

## Definitions

- **Candidate submission**: any valid Kaggle-style submission file (schema matches `sample_submission.csv`).
- **Agent-selected final**: the candidate the agent chooses to place at `submission.csv`.
- **Selection holdout**: a private split used only for choosing among candidates (hidden from the agent).
- **Evaluation holdout**: the private split used for the official benchmark score (hidden from the agent).

## Why this exists

With longer budgets, agents may explore more and end a run with a worse final `submission.csv`, even if a better candidate existed mid-run. This breaks expected monotonic budget scaling and makes it hard to tell whether the failure is:
- inability to improve the model, or
- inability to choose the best candidate.

## Protocol (per run)

### A) Agent responsibilities (no oracle)

The prompt requires the agent to:

1. Write candidate submissions under `submissions/`:
   - `submissions/sub_001.csv`, `submissions/sub_002.csv`, ...
2. Maintain `submissions/summary.json`:
   - `candidates`: list of objects with `{path, local_score, notes, timestamp}` (schema can evolve)
   - `chosen_candidate_path`: which candidate was selected
   - `selection_method`: e.g. “5-fold CV RMSE” or “holdout split AUC”
3. Copy the chosen candidate to the workspace root as `submission.csv`.

### B) Harness responsibilities (selection holdout oracle, not evaluation)

Outside the agent environment, the harness:

1. Validates all candidate submissions.
2. Dedupes candidates by normalized submission hash (avoid counting identical files).
3. Scores each candidate on the **selection holdout**.
4. Chooses the best candidate:
   - `oracle_selected_submission.csv` (stored under run artifacts)

### C) Evaluation (official vs diagnostic)

Always compute:
- `final_eval_score`: score of agent’s `submission.csv` on the **evaluation holdout** (official leaderboard)

Additionally (diagnostic):
- `oracle_selected_eval_score`: score of `oracle_selected_submission.csv` on the evaluation holdout
- `oracle_selected_selection_score`: best score on selection holdout among candidates

Derived diagnostics:
- **Selection regret** = `oracle_selected_eval_score - final_eval_score` (sign depends on metric direction)
- **Search headroom** = `oracle_selected_selection_score - selection_score_of_final`

## Guardrails (avoid “mechanical improvements”)

To avoid “more time → more candidates → best-of-K improves mechanically”:

- Fix a maximum number of candidates per run (e.g. `K=5`), OR
- Report metrics as a function of K (top-1/top-3/top-5), AND
- Deduplicate by normalized hash so resubmitting the same predictions doesn’t count.

Important: `oracle_selected_eval_score` should not replace the official leaderboard score; it is a diagnostic to separate modeling vs selection failures.

## Data layout suggestion

Within a run directory:

- `workspace/submissions/` (agent-written candidates + summary)
- `artifacts/submission.candidates/` (harness-copied, normalized, deduped)
- `artifacts/oracle_selected_submission.csv`
- `artifacts/oracle_selected_submission.normalized.csv`

## DB / result schema (future)

Optionally record in `result.json` (and DB) fields like:
- `candidates_count`
- `candidates_unique_count`
- `final_eval_score` (existing)
- `oracle_selected_eval_score` (diagnostic)
- `oracle_selected_selection_score` (diagnostic)
- `selection_regret`

