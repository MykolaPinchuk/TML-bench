# HANDOFF

## Current slice
v6 paper drafting is complete and merged to `master`.

Current branch initialization for follow-on work is complete:
- local branch: `v6.5`
- base commit: `0dc0ece` (`Merge pull request #10 from MykolaPinchuk/v6`)

The next slice is reviewer-driven revision: collect feedback from external reviewer agents, then apply edits to the draft and claims/evidence trace.

## Current state (2026-03-03)
- Branch state:
  - `origin/master` and local `master` at `0dc0ece`
  - `origin/v6` at `d91b472`
  - working branch for next work: `v6.5`
- Paper artifacts:
  - markdown draft: `docs/paper/draft_v1.md`
  - claims matrix: `docs/paper/claims_matrix_v1.md`
  - LaTeX draft entrypoint: `docs/paper/tex_v1/main.tex`
  - reproducibility appendix: `docs/paper/repro_appendix_v1.md`
- Paper workflow pointers:
  - contract: `docs/paper/PAPER_WORKFLOW.md`
  - writer prompts: `docs/paper/HUMAN_CHEATSHEET.md`
  - writer style/evidence rules: `docs/paper/WRITER_PLAYBOOK.md`
  - active paper state: `docs/paper/PAPER_STATE.md`
- Active evidence bundle for writing is `docs/paper/paper_assets_v2` (`next_assets_dir` is `docs/paper/paper_assets_v3`).
- Canonical baseline status remains healthy (`python3 scripts/check_profiled1_canonical_coverage.py`):
  - `sources_found=9/9`
  - `canonical_models=10`
  - `missing_cells=0`
  - `status=OK`
- No active async benchmark run is currently live.

## Canonical reporting policy (unchanged)
- `results.md` remains complete-model-only canonical reporting (currently 10 models).
- Do not merge partial 14-model results into canonical tables.
- Promote canonical scope to 14 only when each remaining model reaches full 5-run coverage across all 12 cells.

## v6 completion evidence
- Merge to master: `0dc0ece`.
- Final writer-pass commit on `v6`: `d91b472` (`agent14: checkpoint(docs): update abstract`).
- External-facing TeX manuscript is present and buildable from `docs/paper/tex_v1/`.
- Reviewer-facing drafting workflow and playbook are committed (`docs/paper/PAPER_WORKFLOW.md`, `docs/paper/WRITER_PLAYBOOK.md`).

## v6.5 immediate plan
1. Run external reviewer-agent feedback passes on the current draft.
2. Consolidate feedback into a scoped edit list (content, clarity, evidence consistency).
3. Apply edits in `docs/paper/tex_v1/` (and keep markdown/claims synchronized where required).
4. Rebuild PDF and re-validate claims/evidence alignment.
5. Freeze revised bundle (`paper_assets_v3`) only if evidence assets change.

## Deferred items (not in immediate v6.5 unless explicitly requested)
- Result 4 token-efficiency analysis (blocked by missing token/cost telemetry in canonical DBs; current schema only exposes `max_tokens`).
- 14-model backfill promotion into canonical reporting.
- v7 backlog items (non-agentic baselines, deeper literature review framing).

## Key evidence paths
- Canonical results: `results.md`
- Canonical stability companion: `docs/reports/v5_5_canonical10_stability.md`
- Canonical refresh/check scripts:
  - `scripts/refresh_profiled1_results.py`
  - `scripts/check_profiled1_canonical_coverage.py`
- Paper draft sources:
  - `docs/paper/draft_v1.md`
  - `docs/paper/claims_matrix_v1.md`
  - `docs/paper/tex_v1/main.tex`
- Paper workflow and state:
  - `docs/paper/PAPER_WORKFLOW.md`
  - `docs/paper/PAPER_STATE.md`
  - `docs/paper/HUMAN_CHEATSHEET.md`
  - `docs/paper/WRITER_PLAYBOOK.md`
- Active writing evidence bundle:
  - `docs/paper/paper_assets_v2/`

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` as the canonical baseline unless explicitly changed by user request.
- Keep suite safety behavior intact (`orchestrator/suite.py`, including foot-traffic concurrency cap).
