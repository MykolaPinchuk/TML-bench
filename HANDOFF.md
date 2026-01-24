# HANDOFF

## Current slice
v1 (Phase 1): deterministic competition preparation, strict submission validation, and private-holdout scoring (functionality only; not secure). Phase 1 is complete for one real competition (`playground-series-s6e1`).

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
1) Human: PR/merge `v1` into main/master.
2) Start `v2` (Phase 2): run workspace templating and a semi-automated `run_one` that supports manual Kilo VSCode runs + host-side validate/score + result recording.
3) First manual agent run: run Kilo VSCode agent on `playground-series-s6e1` and score it via the orchestrator utilities.

### Open questions
- Which competition/task is first for Phase 1?
- Do we require multiclass support in v1, or start with regression/binary only?
  (Resolved for Phase 1: `playground-series-s6e1` regression only. Multiclass can wait.)

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
