# HANDOFF

## Current slice
v6 draft-first execution (canonical 10-model milestone).

v5.5 closeout is complete; v6 is now in drafting mode using canonical 10-model evidence only.

## Current state (2026-02-11)
- Latest top-up run: `v5_5_topup_remaining5_r5_20260209_r2`.
- Terminal status: `completed` at `2026-02-09 22:36:24 PST`.
- `final_missing`: 0 active missing cells for all profiles.
- `final_deferred`: `simple=52`, `good=45`, `sota=46` runs.
- No active async run is currently live.
- v5.5 canonical reporting artifacts are reproducible and frozen for draft usage.
- v6 branch has been created and fast-forwarded to include all v5.5 closeout commits.
- v6 reproducibility check re-run on 2026-02-11 passed with `status=OK` (`sources_found=9/9`, `canonical_models=10`, `missing_cells=0`).
- v6 draft assets created:
  - `docs/paper/draft_v1.md`
  - `docs/paper/claims_matrix_v1.md`
  - `docs/paper/repro_appendix_v1.md`

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

## v6 plan
- v5.5 closeout plan (completed): `docs/plan/v5_5_closeout.md`.
- v6 draft-first plan (active): `docs/plan/v6.md`.
- Completed deliverables:
  1. D1 draft skeleton and first-pass prose (`docs/paper/draft_v1.md`).
  2. D2 claim-evidence matrix (`docs/paper/claims_matrix_v1.md`).
  3. D3 reproducibility appendix (`docs/paper/repro_appendix_v1.md`).
- Immediate next item:
  1. D4 narrative quality pass: tighten interpretation text, ensure tone/claim precision, and keep all quantitative statements tied to `claims_matrix_v1.md`.

## Deferred expansion gate (non-canonical track)
Retry 14-model backfill only when:
1. circuit-breaker windows for blocked models have aged out, and
2. provider/model health shows acceptable success behavior in fresh attempts.

Until both are true, treat 14-model backfill as deferred work and keep 10-model tables canonical.

## Recommended v6 starting point
1. Use `results.md` canonical 10-model tables as the primary result source.
2. Use `docs/reports/v5_5_canonical10_stability.md` for variability narrative (median + IQR).
3. Use `scripts/refresh_profiled1_results.py` and `scripts/check_profiled1_canonical_coverage.py` as reproducibility commands to cite in the draft appendix.
4. Follow `docs/plan/v6.md` execution order for draft deliverables and exit criteria.

## Key evidence paths
- Canonical report: `results.md`
- Legacy snapshots archive: `docs/archive/results_legacy_snapshots_2026-02-10.md`
- Canonical refresh+verify flow: `scripts/refresh_profiled1_results.py`
- Canonical coverage checker: `scripts/check_profiled1_canonical_coverage.py`
- Stability supplement: `docs/reports/v5_5_canonical10_stability.md`
- v6 plan: `docs/plan/v6.md`
- Draft v1: `docs/paper/draft_v1.md`
- Claims matrix: `docs/paper/claims_matrix_v1.md`
- Repro appendix: `docs/paper/repro_appendix_v1.md`
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
