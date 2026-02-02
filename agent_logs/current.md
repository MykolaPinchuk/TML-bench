# agent_logs/current.md

## Agent
- id: agent08

## Timestamp (Pacific)
- start: 2026-02-01

## Intent
- Next slice: consolidate reporting workflow around `results.md` + baseline default; only run experimental prompt families when explicitly requested.

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).

## Log

### 2026-02-01 18:42:05 PST
- Onboarded on branch `v5` (clean working tree) and reviewed current v5 reporting + prompt-policy decisions.
- Next: keep baseline prompt family as default; treat time-gated/budget-aware as opt-in experiments; prefer `results.md` as the repo-root snapshot and keep root leaderboards opt-in via `--write-leaderboards`.

### 2026-02-01 19:46:23 PST
- v5.5: Added Chutes probe model set `orchestrator/model_sets/v5_5_chutes_try9.json`; preflight filtered to 7/9 passing (`tmp/preflight/v5_5_chutes_try9.filtered.json`).
- Ran 1 competition (`bank-customer-churn-ict-u-ai`) with `--concurrency 2` for `simple-baseline` (240s) + `good-baseline` (600s) into `results/results_v5_5_try9_bank.sqlite`.
- Failures (both budgets): `deepseek-ai/DeepSeek-V3.2-TEE` and `XiaomiMiMo/MiMo-V2-Flash` timed out (no `submission.csv`).

### 2026-02-01 20:22:44 PST
- Completed the remaining 2 models that timed out in 90s preflight via `orchestrator/model_sets/v5_5_chutes_try9_suspect2.json` (same competition/DB, `--concurrency 2`).
- Result: `moonshotai/Kimi-K2-Instruct-0905` succeeded at 240s/600s; `unsloth/gemma-3-27b-it` timed out at 240s/600s (no `submission.csv`).
