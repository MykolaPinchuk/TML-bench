# agent_logs/current.md

## Agent
- id: agent03

## Timestamp (Pacific)
- start: 2026-01-26

## Intent
- Phase 4 (v4): continue reproducibility packaging and baseline/sweep policy iteration.

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).

## Log

- 2026-01-25 16:43:48 PST: Onboarded v4 branch. Current focus is Phase 4 reproducibility + sweep reliability: headless runs via `orchestrator.run_one auto`/`orchestrator.sweep` (profiles `simple-baseline`=240s, `good-baseline`=600s), with provenance hashes and collision/variance surfaced in `LEADERBOARD.md`. Next likely work: reduce `simple-baseline` collisions/timeouts by adjusting prompt profile/timeout or adding light diversity, while keeping docs (`REPRODUCIBILITY.md`) and DB schema (`orchestrator/db.py`) consistent.
- 2026-01-25 17:31:13 PST: Prepared `bank-customer-churn-ict-u-ai` and ran 1 smoke + 1x v3_fast sweep (8 models) at 240s `simple-baseline` budget; all 9 runs succeeded. Wrote a per-competition health report to `results/health.md` and refreshed leaderboards.
- 2026-01-25 17:44:09 PST: Added an "Overall (across competitions)" aggregation to `LEADERBOARD.md` and fixed best-run selection to use higher-is-better normalized scoring (important for metrics like AUC). Regenerated `LEADERBOARD.*` and `results/leaderboard.*`.
- 2026-01-25 18:01:41 PST: Added baseline normalization anchored to two host baselines (`constant` + `hgb`). New CLI: `python -m orchestrator.baselines --competition-id <id>` records baseline scores into `results/results.sqlite`, and the "Overall" leaderboard table now includes absolute columns (`mean_abs_units`, `beat_hgb_rate`).
- 2026-01-26 15:41:26 PST: Checkpointed regenerated leaderboard artifacts (`9583af5`). Attempted to prepare `applied-regression-on-structured-attributes` with Kaggle CLI, but download returned `403 Forbidden` (likely needs competition rule acceptance in browser). Regenerated `python -m orchestrator.report` and `python -m orchestrator.leaderboard --write-root` successfully with no diff.
