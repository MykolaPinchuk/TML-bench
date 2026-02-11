# Frozen prompt strategies

This folder holds **immutable** prompt strategy definitions (single-word ids).

Rule: once a strategy id is used in `results.md`, **do not edit it**. If you want to change prompt text, create a new id (e.g. `profiled2`) and use that going forward.

Current strategy ids:
- `legacy1`: “base+override” (no profile layer).
- `profiled1`: “base+profile+override” using the baseline profiles (`simple-baseline`, `good-baseline`, `sota-xgb`).

Notes:
- The “live” prompt files under `prompts/` may evolve. Use them for development only.
- For reproducible experiments and paper-grade results, always run a **frozen** strategy id from `prompts/strategies/`.

