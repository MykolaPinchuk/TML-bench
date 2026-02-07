# HANDOFF

## Current slice
v5.5 reliability + replication top-up for 3 models under Strategy 2 (`profiled1`) to reach 5 successful runs per cell.

Models:
- `chutes::moonshotai/Kimi-K2-Instruct-0905`
- `chutes::openai/gpt-oss-120b-TEE`
- `chutes::zai-org/GLM-4.7-FP8`

Canonical inputs:
- Suite: `orchestrator/suites/v5_all.json`
- Model set: `orchestrator/model_sets/v5_5_topup_kimi_gptoss_glm47fp8.json`
- DB: `results/results_v5_5_topup3models_r5.sqlite`
- Mode: `v5_5_topup3models_r5`

## Active run (live)
- run_name: `v5_5_topup3models_r5_20260206_r5`
- status (last check): running/alive
- check timestamp: 2026-02-06 16:32:17 PST
- status command:
  - `python scripts/async_suite_runner.py status --run-name v5_5_topup3models_r5_20260206_r5`
- log:
  - `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/run.log`
- status file:
  - `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/status.json`
- events:
  - `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/events.jsonl`
- postmortem target:
  - `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/postmortem.md`

Current DB missing-success snapshot (`prompt_strategy=profiled1`):
- `simple-baseline`: missing_cells=4, missing_runs=13
- `good-baseline`: missing_cells=12, missing_runs=49
- `sota-xgb`: missing_cells=12, missing_runs=44

## What changed this cycle
1. Async reliability hardening and RCA tooling:
- `scripts/async_suite_runner.py` improved with stronger diagnostics/postmortems.

2. Confirmed root causes for prior failures:
- systemd PATH propagation issue (`kilo` not found) fixed.
- true OOM incident on `v5_5_topup3models_r5_20260206_r4` confirmed via systemd/kernel evidence.

3. OOM mitigation shipped:
- `orchestrator/suite.py` now applies a safety cap:
  - `foot-traffic-wuerzburg-retail-forecasting-2-0` forced to `concurrency=1`
  - others retain requested/default concurrency.

4. Paper planning docs:
- Added `misc_paper_ideas.md` (v1 paper angles, hypotheses, telemetry audit, record-now checklist).
- Linked from `REPO_MAP.md`.

5. Token telemetry audit:
- Token/cost fields are usually present when JSONL exists.
- Overall token coverage is low mostly because many historical runs have no JSONL artifacts.
- A few missing-usage cases are consistent with 200k stdout truncation.

## Key evidence paths
OOM RCA evidence:
- `tmp/async_runs/v5_5_topup3models_r5_20260206_r4/postmortem.md`

Active run evidence:
- `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/run.log`
- `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/status.json`
- `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/events.jsonl`

## Next actions
1. Keep monitoring `r5` until completion/failure.
2. Immediately after completion/failure:
- `python scripts/async_suite_runner.py diagnose --run-name v5_5_topup3models_r5_20260206_r5`
3. If incomplete, relaunch with same DB/mode to resume missing-success cells.
4. Once stable, update `results.md` with refreshed 5-run medians.
5. For paper prep, start implementing token/cost sidecar extraction from `kilo_stdout.clean.jsonl`.

## Invariants (do not break)
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` as baseline default unless user explicitly asks otherwise.
- Do not launch new long runs without diagnosable logs/postmortem path.

## .gitignore check
- `.gitignore` remains strict for:
  - `runs/**`
  - `tmp/**`
  - `results/**` (except `results/README.md`)
  - competition `public/private/raw/downloads`
  - secrets/key material

## Git evidence
Relevant commits in this cycle:
- `b78555c` — checkpoint: async RCA hardening + foot-traffic concurrency cap
- `a343eee` — previous handoff commit
- `74a8be8` — checkpoint: paper ideas + telemetry roadmap
