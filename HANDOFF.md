# HANDOFF

## Current slice
v1 (Phase 1): implement deterministic competition preparation, strict submission validation, and private-holdout scoring (functionality only; not secure).

## Invariants (do not break)
- No secrets or credentials in git.
- No Kaggle datasets / generated competition data in git.
- No run artifacts (submissions, transcripts, workspaces) in git.
- Phase branches: work progresses on `v0`, then `v1`, `v2`, ... (human pushes).

## State of work

### Done (with evidence)
- PRD exists: `prd.md`.
- Agentic workflow scaffolding (this set of files): `repo_workflow.md`, `onboarding.md`, `HANDOFF.md`, `REPO_MAP.md`, `agent_logs/`.
- Phase 1 LLD written: `docs/plan/v1.md`.
- Phase 1 core implemented + tested:
  - `orchestrator/schemas.py`, `orchestrator/prepare_lib.py`, `orchestrator/validate.py`, `orchestrator/score.py`
  - toy competition for fixtures: `competitions/toy_regression/`
  - tests: `tests/test_prepare_validate_score.py` (run: `pytest -q`)

### Next (ordered)
1) Select the first real competition/task id (tabular, small, post-cutoff) and add `competitions/<id>/spec.yaml` + `prepare_competition.py`.
2) Extend `prepare_holdout_from_train` to support `split.strategy: group|time` if needed by the selected task.
3) Start Phase 2 scaffolding (runs workspace template + result record) once Phase 1 is stable for one real task.

### Open questions
- Which competition/task is first for Phase 1?
- Do we require multiclass support in v1, or start with regression/binary only?

## Repro / smoke check
- Commands run:
  - `git status -sb`
- Outcome:
  - Repo is in setup phase; no code executed yet.

## Known issues / current breakage
- None known.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
