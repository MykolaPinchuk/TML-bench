# HANDOFF

## Current slice
v5.5 closeout for baseline reporting under Strategy 2 (`profiled1`).

Canonical scope is now the fully complete 10-model set (5 successful runs/cell across `4 competitions x 3 profiles`), while the remaining 4-model expansion is deferred.

## Current state (2026-02-10)
- Latest top-up run: `v5_5_topup_remaining5_r5_20260209_r2`.
- Terminal status: `completed` at `2026-02-09 22:36:24 PST`.
- `final_missing`: 0 active missing cells for all profiles.
- `final_deferred`: `simple=52`, `good=45`, `sota=46` runs.
- No active async run is currently live.

Combined14 completion snapshot:
- complete models: `10/14`
- remaining missing runs: `143`
- incomplete models:
  - `chutes::microsoft/Phi-3.5-mini-instruct` (`56`)
  - `chutes::meta-llama/Meta-Llama-3.1-8B-Instruct` (`50`)
  - `openrouter::x-ai/grok-4.1-fast` (`29`)
  - `chutes::moonshotai/Kimi-K2-Instruct-0905` (`8`)

## Canonical reporting policy (v5.5)
- `results.md` publishes complete-model-only canonical tables (currently 10 models).
- Do not merge partial 14-model results into canonical tables.
- Promote canonical scope to 14 only when each remaining model reaches full 5-run coverage across all 12 cells.

## v5.5 closeout plan
- Detailed plan: `docs/plan/v5_5_closeout.md`.
- High-priority next items:
  1. Add reproducibility lock/checker for canonical 10-model coverage.
  2. Add compact stability/context supplement without expanding canonical scope.
  3. Keep state docs synchronized with terminal run state and deferred expansion gate.

## Deferred expansion gate (non-canonical track)
Retry 14-model backfill only when:
1. circuit-breaker windows for blocked models have aged out, and
2. provider/model health shows acceptable success behavior in fresh attempts.

Until both are true, treat 14-model backfill as deferred work and keep 10-model tables canonical.

## Key evidence paths
- Canonical report: `results.md`
- Legacy snapshots archive: `docs/archive/results_legacy_snapshots_2026-02-10.md`
- Closeout plan: `docs/plan/v5_5_closeout.md`
- Latest run status: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/status.json`
- Latest run events: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/events.jsonl`
- Latest run postmortem: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/postmortem.md`

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` as the baseline default unless explicitly changed by user request.
- Use `scripts/async_suite_runner.py` for long async runs.
- Keep suite safety behavior intact (`orchestrator/suite.py`, including foot-traffic cap).
