# HANDOFF

## Current slice
v5.5 reliability + replication top-up for 3 newer models to reach 5 runs/cell under Strategy 2 (`profiled1`):
- `moonshotai/Kimi-K2-Instruct-0905`
- `openai/gpt-oss-120b-TEE`
- `zai-org/GLM-4.7-FP8`

Canonical model set for this batch:
- `orchestrator/model_sets/v5_5_topup_kimi_gptoss_glm47fp8.json`

Canonical suite:
- `orchestrator/suites/v5_all.json` (4 competitions)

Primary DB/mode:
- `results/results_v5_5_topup3models_r5.sqlite`
- mode: `v5_5_topup3models_r5`

## What changed in this cycle
1. Root-cause logging and postmortem tooling were hardened in `scripts/async_suite_runner.py`:
- structured `events.jsonl`
- heartbeat/status reconciliation
- `diagnose`/`reconcile`
- systemd diagnostics in postmortem (memory + journal tail)

2. Concrete detached-run failure root causes were identified and persisted:
- Missing `PATH` in systemd launch caused `FileNotFoundError: 'kilo'` (fixed by env propagation).
- True OOM kill on `v5_5_topup3models_r5_20260206_r4` confirmed via systemd+kernel evidence.

3. OOM mitigation implemented:
- `orchestrator/suite.py` now applies a per-competition safety cap:
  - `foot-traffic-wuerzburg-retail-forecasting-2-0` forced to `concurrency=1`
  - other competitions keep requested/default concurrency.

4. Documentation of failure pattern + mitigation was promoted to top-level docs:
- `a2a_notes.md`
- `README.md`
- `REPO_MAP.md`
- `agent_logs/current.md`

## Active long run (live)
Current async run:
- run_name: `v5_5_topup3models_r5_20260206_r5`
- status: running (last checked: 2026-02-06 15:31 PST)
- run dir: `tmp/async_runs/v5_5_topup3models_r5_20260206_r5`
- log: `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/run.log`
- status file: `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/status.json`
- events: `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/events.jsonl`
- postmortem (when done): `tmp/async_runs/v5_5_topup3models_r5_20260206_r5/postmortem.md`

Evidence from current log:
- Bank completed with resume.
- Foot-traffic stage started with applied cap:
  - `note: applying safe concurrency cap for foot-traffic-wuerzburg-retail-forecasting-2-0: requested=3 effective=1`

## Failure RCA evidence (important)
OOM incident (do not ignore):
- Run: `v5_5_topup3models_r5_20260206_r4`
- Postmortem: `tmp/async_runs/v5_5_topup3models_r5_20260206_r4/postmortem.md`
- systemd status evidence: `Result=oom-kill`, `MemoryPeak=20909871104`
- systemd journal evidence included in postmortem
- kernel evidence captured during RCA (killed process in this unit cgroup; high anon RSS)

Likely trigger pattern:
- `foot-traffic` + generated scripts that one-hot encode `id` (very high cardinality) + parallelism.

## Current completion snapshot (top-up DB, Strategy 2)
From `results/results_v5_5_topup3models_r5.sqlite` (mode `v5_5_topup3models_r5`, prompt_strategy `profiled1`):
- simple-baseline: missing_cells=4, missing_runs=17
- good-baseline: missing_cells=12, missing_runs=49
- sota-xgb: missing_cells=12, missing_runs=44

Notes:
- The active `r5` run is still progressing; numbers above are a pre-completion snapshot.

## Next actions for next agent
1. Monitor `r5` until completion/failure.
2. Immediately run:
- `python scripts/async_suite_runner.py diagnose --run-name v5_5_topup3models_r5_20260206_r5`
3. If `r5` fails, extract root cause from:
- `status.json`
- `events.jsonl`
- `postmortem.md`
- log tail
4. Resume with same DB/mode (do not fork mode) until missing cells are filled.
5. Refresh `results.md` after stable completion snapshot.

## Invariants
- Do not commit datasets, runs, sqlite DBs, or secrets.
- Keep `profiled1` as baseline default unless user explicitly asks otherwise.
- Do not start a new long run without diagnosable logging/postmortem capability.

## Useful commands
Monitor live run:
- `python scripts/async_suite_runner.py status --run-name v5_5_topup3models_r5_20260206_r5`
- `tail -f tmp/async_runs/v5_5_topup3models_r5_20260206_r5/run.log`

Post-run diagnosis:
- `python scripts/async_suite_runner.py diagnose --run-name v5_5_topup3models_r5_20260206_r5`
- `python scripts/async_suite_runner.py reconcile`

## Git evidence
Latest checkpoint before this handoff:
- `b78555c` — `agent09: checkpoint(workflow): harden async RCA and cap foot-traffic concurrency`
