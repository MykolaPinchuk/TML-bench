# HANDOFF

## Current slice
v5.5 reliability + replication top-up for the remaining incomplete combined14 models under Strategy 2 (`profiled1`) toward 5 successful runs/cell.

Models in current top-up set:
- `chutes::tngtech/DeepSeek-TNG-R1T2-Chimera`
- `chutes::moonshotai/Kimi-K2-Instruct-0905`
- `openrouter::x-ai/grok-4.1-fast`
- `chutes::meta-llama/Meta-Llama-3.1-8B-Instruct`
- `chutes::microsoft/Phi-3.5-mini-instruct`

Canonical inputs:
- Suite: `orchestrator/suites/v5_all.json`
- Model set: `orchestrator/model_sets/v5_5_topup_remaining5_r5.json`
- DB: `results/results_v5_5_topup_remaining5_r5_seeded.sqlite`
- Mode: `v5_5_topup_remaining5_r5`

## Active run (live)
- run_name: `v5_5_topup_remaining5_r5_20260209_r1`
- status (last check): `running/alive`, `current_profile=sota-xgb`, `current_attempt=1`
- check timestamp: 2026-02-09 15:29:21 PST
- status command:
  - `python scripts/async_suite_runner.py status --run-name v5_5_topup_remaining5_r5_20260209_r1`
- log:
  - `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/run.log`
- status file:
  - `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/status.json`
- events:
  - `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/events.jsonl`
- postmortem target:
  - `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/postmortem.md`

Current DB missing-success snapshot (`prompt_strategy=profiled1`, mode `v5_5_topup_remaining5_r5`):
- `simple-baseline` (240s): missing_total=52, active=27, deferred=25
- `good-baseline` (600s): missing_total=48, active=17, deferred=31
- `sota-xgb` (1200s): missing_total=47, active=0, deferred=47
- overall: missing_total=147, active=44, deferred=103

Current circuit-breaker blocks (24h window, threshold=3):
- `simple-baseline`: `microsoft/Phi-3.5-mini-instruct`, `x-ai/grok-4.1-fast`
- `good-baseline`: `microsoft/Phi-3.5-mini-instruct`, `x-ai/grok-4.1-fast`
- `sota-xgb`: `Meta-Llama-3.1-8B-Instruct`, `microsoft/Phi-3.5-mini-instruct`, `x-ai/grok-4.1-fast`

## What changed this cycle
1. Hardened async launcher for OOM/session resilience:
- `scripts/async_suite_runner.py` now sets systemd `MemoryHigh=16G`, `MemoryMax=22G`, `Restart=on-failure`, `RestartSec=30s`.

2. Completed Wave B restart successfully:
- run `v5_5_topup3_waveB_r5_20260209_r3` finished with `final_missing=0` and only deferred gaps.

3. Added dedicated remaining-model top-up set:
- new file `orchestrator/model_sets/v5_5_topup_remaining5_r5.json`.

4. Seeded dedicated remaining-model DB/mode and launched new run:
- `results/results_v5_5_topup_remaining5_r5_seeded.sqlite`
- mode `v5_5_topup_remaining5_r5`
- launched `v5_5_topup_remaining5_r5_20260209_r1`.

5. Reclaimed disk safely for historical runs while preserving metadata:
- removed completed-run `workspace/public` copies and duplicate `workspace/submission.csv` where `artifacts/submission.csv` exists.
- `runs/` reduced from ~80G to ~30G.

## Key evidence paths
Active run evidence:
- `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/run.log`
- `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/status.json`
- `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r1/events.jsonl`

Completed Wave B evidence:
- `tmp/async_runs/v5_5_topup3_waveB_r5_20260209_r3/postmortem.md`
- `tmp/async_runs/v5_5_topup3_waveB_r5_20260209_r3/status.json`

Updated launcher implementation:
- `scripts/async_suite_runner.py`

## Next actions
1. Continue monitoring `v5_5_topup_remaining5_r5_20260209_r1` until terminal state.
2. On completion/failure, run:
- `python scripts/async_suite_runner.py diagnose --run-name v5_5_topup_remaining5_r5_20260209_r1`
3. If `final_missing > 0`, relaunch with same DB/mode/model-set to resume remaining active cells.
4. Keep deferred cells deferred unless provider/model recovers beyond circuit-breaker window; then run another top-up pass.
5. After meaningful completion gains, refresh 5-run-only tables:
- `python scripts/update_profiled1_fiverun_tables.py`

## Invariants (do not break)
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` baseline default unless user explicitly asks otherwise.
- For long runs, use `scripts/async_suite_runner.py start` with diagnosable logs/status/events/postmortem.
- Keep foot-traffic safety cap behavior intact (`orchestrator/suite.py`).

## .gitignore check
- `.gitignore` remains strict for:
  - `runs/**`
  - `tmp/**`
  - `results/**` (except `results/README.md`)
  - competition `public/private/raw/downloads`
  - secrets/key material

## Git evidence
Recent commits in this cycle:
- `edfaff0` — checkpoint: add remaining5 top-up model set
- `fe23ad3` — checkpoint: log Wave B completion + storage cleanup
- `df951d6` — checkpoint: async launcher memory/restart hardening + 5-run table refresh tooling
