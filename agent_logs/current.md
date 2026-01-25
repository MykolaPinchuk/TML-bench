# agent_logs/current.md

## Agent
- id: agent02

## Timestamp (Pacific)
- start: 2026-01-24

## Intent
- Phase 4 (v4): reproducibility packaging + baselines (pin deps, provenance capture, rerun docs; baseline injection becomes optional smoke/debug, not default for sweeps).

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).

## Log

### 2026-01-25 (Pacific) — Onboard
- Read repo index/state docs; current slice is Phase 4 (v4): reproducibility packaging + baselines.
- Opened `orchestrator/run_one.py`, `orchestrator/sweep.py`, `orchestrator/result.py`, `orchestrator/db.py`, `orchestrator/kilo_cli.py`, and Phase 3+/4 plan (`docs/plan/v3.md`) to identify where to add provenance + version pinning.
- Verified local sanity: `pytest -q` (6 passed).
- Next steps: pin Python/Kilo versions, expand provenance (prompt/spec/data hashes), and separate “host baseline” from default sweep behavior.

### 2026-01-25 (Pacific) — Baseline seeding made optional
- Changed `run_one auto` / `sweep` so baseline `train_model.py` seeding is opt-in via `--seed-baseline` (to avoid identical “baseline-driven” scores in benchmark sweeps).

### 2026-01-25 (Pacific) — Provenance capture (Phase 4)
- Added per-run provenance capture (spec/prompt/public manifest hashes; Kilo version; redacted Kilo config hash) into `result.json` + sqlite DB, and wrote `runs/<run_id>/artifacts/public_manifest.json`.
- Refreshed root leaderboard; added a “Duplicate submissions” section to make identical outputs obvious.
