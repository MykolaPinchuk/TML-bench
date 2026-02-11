# HANDOFF

## Current slice
v5.5 closeout complete for baseline reporting under Strategy 2 (`profiled1`).

Canonical scope is now the fully complete 10-model set (5 successful runs/cell across `4 competitions x 3 profiles`), while the remaining 4-model expansion is deferred.

## Current state (2026-02-10)
- Latest top-up run: `v5_5_topup_remaining5_r5_20260209_r2`.
- Terminal status: `completed` at `2026-02-09 22:36:24 PST`.
- `final_missing`: 0 active missing cells for all profiles.
- `final_deferred`: `simple=52`, `good=45`, `sota=46` runs.
- No active async run is currently live.
- v5.5 canonical reporting artifacts are now reproducible via scripts and ready for v6 drafting.

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
- Completed this cycle:
  1. Reproducibility lock/checker implemented:
     - `scripts/check_profiled1_canonical_coverage.py`
     - `scripts/refresh_profiled1_results.py`
  2. Stability companion report implemented:
     - `scripts/render_profiled1_canonical_stability.py`
     - `docs/reports/v5_5_canonical10_stability.md`
- High-priority next items:
  1. Start v6 draft writing using canonical 10-model artifacts only.
  2. Keep 14-model backfill explicitly out of draft claims unless full completion criteria are later met.
  3. If/when backfill resumes, keep canonical 10-model tables unchanged until 14-model completion criteria are fully met.

## Deferred expansion gate (non-canonical track)
Retry 14-model backfill only when:
1. circuit-breaker windows for blocked models have aged out, and
2. provider/model health shows acceptable success behavior in fresh attempts.

Until both are true, treat 14-model backfill as deferred work and keep 10-model tables canonical.

## Recommended v6 starting point
1. Use `results.md` canonical 10-model tables as the primary result source.
2. Use `docs/reports/v5_5_canonical10_stability.md` for variability narrative (median + IQR).
3. Use `scripts/refresh_profiled1_results.py` and `scripts/check_profiled1_canonical_coverage.py` as reproducibility commands to cite in the draft appendix.

## Key evidence paths
- Canonical report: `results.md`
- Legacy snapshots archive: `docs/archive/results_legacy_snapshots_2026-02-10.md`
- Canonical refresh+verify flow: `scripts/refresh_profiled1_results.py`
- Canonical coverage checker: `scripts/check_profiled1_canonical_coverage.py`
- Stability supplement: `docs/reports/v5_5_canonical10_stability.md`
- Closeout plan: `docs/plan/v5_5_closeout.md`
- Latest run status: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/status.json`
- Latest run events: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/events.jsonl`
- Latest run postmortem: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/postmortem.md`
- Recent closeout commits:
  - `a2a25cb` — canonical refresh/check/stability tooling
  - `b95e907` — v5.5 closeout plan + handoff refresh
  - `6f53a21` — explicit 10-model reporting policy

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` as the baseline default unless explicitly changed by user request.
- Use `scripts/async_suite_runner.py` for long async runs.
- Keep suite safety behavior intact (`orchestrator/suite.py`, including foot-traffic cap).
