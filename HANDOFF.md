# HANDOFF

## Current slice
v2 (Phase 2): manual Kilo VSCode runs with repeatable run workspaces + host-side finalize (validate/score/record). Phase 1 is already complete for `playground-series-s6e1`.

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
- Real competition wired in (Kaggle):
  - `competitions/playground-series-s6e1/spec.yaml`, `competitions/playground-series-s6e1/prepare_competition.py`
  - canonical prep policy: `docs/adr/0002-canonical-competition-prep.md`
  - Phase 1 smoke: `KAGGLE_CONFIG_DIR=secrets python scripts/smoke_phase1.py --competition-id playground-series-s6e1`

### Next (ordered)
1) Use `python -m orchestrator.run_one create --competition-id playground-series-s6e1` to create a run workspace.
2) Human: run Kilo VSCode agent inside the workspace and produce `submission.csv`.
3) Finalize and record: `python -m orchestrator.run_one finalize --competition-id playground-series-s6e1 --run-id <run_id>`.

### Open questions
- Do we want SQLite recording in Phase 2, or keep Phase 2 as `result.json` only?

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
