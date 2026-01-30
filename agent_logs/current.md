# agent_logs/current.md

## Agent
- id: agent06

## Timestamp (Pacific)
- start: 2026-01-30

## Intent
- Onboard repo state (v5), identify next slice, and prepare to run/refresh the Phase 5 suite leaderboard.

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).

## Log

- 2026-01-30 (Pacific): New cycle started after handoff log rotation.
- 2026-01-30 (Pacific): Onboarded index files + hot paths (suite/sweep/run_one/kilo_cli/leaderboard). Next: run `python -m orchestrator.suite ... --resume` to refresh snapshots, or iterate on provider/model reliability classification if runs are flaky.
- 2026-01-30 (Pacific): Suite `v5_core` `simple-baseline` `v3_fast` `runs_per_model=2 --resume`: scheduled 1 run (`playground-series-s5e10_3c748e5e6a60` chutes/GLM-4.6-FP8) and it timed out with no `submission.csv` (recorded result + refreshed leaderboards).
- 2026-01-30 (Pacific): Debug: the timed-out GLM run has **zero** `ask: command` tool events in `runs/playground-series-s5e10_3c748e5e6a60/artifacts/kilo_stdout.clean.jsonl` (model streamed reasoning only), explaining the missing `submission.csv`.
- 2026-01-30 (Pacific): Preflight iteration: bumped preflight default timeout to 90s and removed ambiguous wording so models don’t get stuck “reasoning about the instructions”; rerunning `python -m orchestrator.preflight --only-provider nanogpt/chutes` now passes consistently with tool calls.
- 2026-01-30 (Pacific): Implemented robust leaderboard view (`LEADERBOARD_ROBUST.md/html`) ranking by per-competition median-of-successes + uncertainty (`rank_pct_p25/p50/p75`) and an expected rank that treats no-success competitions as worst (100%).
- 2026-01-30 (Pacific): Implemented experimental iterative headless mode (`--iterative`, `mode=iter2stage`) with a submission validity guard that snapshots/restores last-known-valid `submission.csv` (no score-based oracle).
- 2026-01-30 (Pacific): Ran experiment sweep: `python -m orchestrator.sweep --competition-id playground-series-s6e1 --profile sota-xgb --iterative --mode iter2stage --concurrency 2 --resume-any-status` (8 models). Outcome: 7/8 succeeded; `nanogpt::mistralai/devstral-2-123b-instruct-2512` timed out with no submission.
- 2026-01-30 (Pacific): Added new Chutes model candidates (`v5_new_models_candidates.json`) and preflighted all 6 successfully. Quick 240s smoke on `playground-series-s6e1` (mode `newmodels`) succeeded for 4/6; `Kimi-K2-Thinking-TEE` and `MiMo-V2-Flash` were toolless/timeouts in non-iterative mode.
- 2026-01-30 (Pacific): Retried the 2 flaky models with `--iterative` (mode `newmodels_iter+iter2stage`); both succeeded within 240s. Wrote a consolidated set: `orchestrator/model_sets/v5_new_models_working.json`.
- 2026-01-30 (Pacific): Tested new models on `playground-series-s6e1` under `good-baseline` (600s) with `--iterative` (mode `newmodels_gb+iter2stage`): 6/6 succeeded; MiMo V2 Flash scored much worse than the others on this task.
