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

### 2026-01-25 (Pacific) — Headless run reliability fixes
- Fixed provenance prompt hashing to point at `workspace/RUN_INSTRUCTIONS.md` (not the run dir).
- Headless `run_one auto` now stops Kilo as soon as `submission.csv` appears, improving success rates under tight budgets.
- Headless runtime accounting now uses Kilo duration (when available) instead of submission mtime, avoiding under-counting.

### 2026-01-25 (Pacific) — No-baseline headless runs
- Adjusted headless Kilo prompt to be shorter (read `RUN_INSTRUCTIONS.md` + focused harness rules) to improve compliance and avoid “stalling”.
- Verified a no-baseline headless run can succeed (`playground-series-s6e1_ee85d335af8b`) and recorded distinct submission hashes vs. prior baseline-seeded runs.

### 2026-01-25 (Pacific) — Baseline removal (v4)
- Removed baseline seeding mode entirely (`--seed-baseline` removed); headless runs always start from scratch with an empty workspace (plus `public/` inputs).

### 2026-01-25 (Pacific) — Collision investigation + sweep robustness
- Relaxed the headless harness prompt to avoid over-prescribing a single “fast HGB baseline” and removed the default “stop immediately on first submission” behavior (`orchestrator/run_one.py`); added `run_one auto --stop-when-submission` for quick smoke runs.
- Fixed Kilo process cleanup so timeouts don’t leave `python train_model.py` running and writing `submission.csv` *after* the orchestrator records a timeout (kill the whole process group; `orchestrator/kilo_cli.py`).
- Reran no-baseline probes:
  - `v4_expanded_probe.json` sweep @240s, concurrency=3: 7/10 success; scores showed more dispersion than previous stop-on-submission runs, but some submission hash collisions remain.
  - Added working models and ran `v4_probe_added.json` sweep @240s: 3/4 success; one more “baseline-like” collision observed (same normalized submission hash across multiple models).
