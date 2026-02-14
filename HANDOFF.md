# HANDOFF

## Current slice
v6 draft-first execution complete for asset prep (canonical 10-model milestone).

v5.5 closeout is complete; v6 now has a ready handoff bundle so the next agent can structure manuscript production and write the first full draft.

## Current state (2026-02-14)
- Latest top-up run: `v5_5_topup_remaining5_r5_20260209_r2`.
- Terminal status: `completed` at `2026-02-09 22:36:24 PST`.
- `final_missing`: 0 active missing cells for all profiles.
- `final_deferred`: `simple=52`, `good=45`, `sota=46` runs.
- No active async run is currently live.
- v5.5 canonical reporting artifacts are reproducible and frozen for draft usage.
- v6 drafting artifacts prepared and committed:
  - manuscript + claim tracing: `docs/paper/draft_v1.md`, `docs/paper/claims_matrix_v1.md`
  - reproducibility appendix: `docs/paper/repro_appendix_v1.md`
  - committed figures/tables for Result 0.5/1/2/3: `docs/paper/figures/v6/`
  - flat staging bundle for next-agent writing pass: `docs/paper/paper_assets_v1/`
- Result 4 (token efficiency) is explicitly deferred for draft2 (not required for draft1) pending token/cost instrumentation.
- Workflow hardening landed: onboarding/checkpoint/handoff now require kickoff `AgentNN` sync into `agent_logs/current.md` before commit flows (commit `c9845e9`).

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
- D4 narrative pass status:
  1. Key findings section added and linked to figures/claims.
  2. Result 0.5/2/3 figure stack generated and checked in.
  3. Result 4 token note added: deferred to draft2.
- Immediate next item (for next agent):
  1. Define and execute structured paper-writing workflow.
  2. Produce first full draft manuscript using `docs/paper/paper_assets_v1/`.
  3. Preserve claim-evidence traceability (`docs/paper/claims_matrix_v1.md`) while moving material into publication structure.

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
- Committed figures: `docs/paper/figures/v6/`
- Staging bundle for paper assembly: `docs/paper/paper_assets_v1/`
- Leaderboard plot generator: `scripts/render_v6_leaderboard_plots.py`
- Key-result plot generator (Result 0.5/2/3): `scripts/render_v6_key_results_plots.py`
- Workflow trigger + identity sync policy: `repo_workflow.md`, `onboarding.md`, `.codex/skills/{onboard,checkpoint,handoff}/SKILL.md`
- Closeout plan: `docs/plan/v5_5_closeout.md`
- Latest run status: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/status.json`
- Latest run events: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/events.jsonl`
- Latest run postmortem: `tmp/async_runs/v5_5_topup_remaining5_r5_20260209_r2/postmortem.md`
- Recent closeout commits:
  - `a2a25cb` — canonical refresh/check/stability tooling
  - `b95e907` — v5.5 closeout plan + handoff refresh
  - `6f53a21` — explicit 10-model reporting policy
- Recent v6 drafting commits:
  - `bc8f8dd` — key findings + narrative tightening
  - `9a57073` — defer Result 4 tokens to draft2
  - `0bd616c` — add consolidated `paper_assets_v1` bundle
  - `c9845e9` — enforce kickoff AgentNN id sync for checkpoint/handoff safety

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` as the baseline default unless explicitly changed by user request.
- Use `scripts/async_suite_runner.py` for long async runs.
- Keep suite safety behavior intact (`orchestrator/suite.py`, including foot-traffic cap).
