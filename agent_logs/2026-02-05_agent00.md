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

### 2026-02-02 07:10:18 PST
- v5.5: Identified “working” Chutes models and wrote `orchestrator/model_sets/v5_5_chutes_working6.json` (6 models).
- Ran full v5_core suite (4 competitions) for the working6 set across all 3 baseline profiles into `results/results_v5_5_working6_suite.sqlite`:
  - `simple-baseline` (240s), `good-baseline` (600s), `sota-xgb` (1200s)
  - `--concurrency 3`, `--runs-per-model 1`, `--mode v5_5_working6`, `--resume` (success-only)
- Notable failures under `mode=v5_5_working6`:
  - 240s: `openai/gpt-oss-120b-TEE` timed out on `playground-series-s5e10` (no `submission.csv`).
  - 1200s: `moonshotai/Kimi-K2-Instruct-0905` timed out on `foot-traffic-wuerzburg-retail-forecasting-2-0`.
  - 1200s: `mistralai/Devstral-2-123B-Instruct-2512-TEE` timed out on `playground-series-s6e1`.
  - 1200s: `tngtech/DeepSeek-TNG-R1T2-Chimera` had one `runtime_error` attempt on `bank-customer-churn-ict-u-ai` but also a success (2 runs for that config).
- Ran “retry1” single-model reruns under `mode=v5_5_working6_retry1` to confirm the 3 timeouts can succeed; all 3 succeeded.
- Wrote health reports to:
  - `tmp/reports/v5_5_working6_suite.md`
  - `tmp/reports/v5_5_working6_suite_with_retries.md`

### 2026-02-02 13:51:43 PST
- Documentation pass: clarified the two prompt rendering strategies (legacy base+override vs current base+profile+override) so `results.md` snapshots aren’t misread as apples-to-apples.

### 2026-02-04 16:51:34 PST
- Started controlled apples-to-apples dataset for **old5** (the `v3_fast.json` 5-model set) under **Strategy 1 = `legacy1`**, 2 runs/cell across the full v5_core suite.
- Command runner: `python -m orchestrator.suite` (3 profiles, `--runs-per-model 2`, `--prompt-strategy legacy1`, `--concurrency 4`, `--resume --resume-any-status`).
- DB (not committed): `results/results_v5_5_v3fast_legacy1_r2.sqlite`
- Mode: `v5_5_v3fast_legacy1_r2`
- Log: `tmp/logs/v3fast_legacy1_r2_20260205T005134Z.log`
- PID: `1554878`

### 2026-02-04 19:00:00 PST
- Completed controlled apples-to-apples dataset for **old5** under **Strategy 1 = `legacy1`** (2 runs/cell across v5_core).
- DB (not committed): `results/results_v5_5_v3fast_legacy1_r2.sqlite` (mode `v5_5_v3fast_legacy1_r2`).
- `results.md` updated to include combined11 tables and a dedicated old5 legacy1 snapshot, plus a brief strategy comparison summary.
