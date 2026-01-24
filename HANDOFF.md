# HANDOFF

## Current slice
v3 (Phase 3): batch execution harness (headless), starting with a Kilo CLI capability spike.

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
- Phase 2 manual-run harness:
  - run lifecycle: `python -m orchestrator.run_one create/start/finalize`
  - optional retroactive metadata: `python -m orchestrator.run_one annotate`
  - enforced time budget at finalize (per `competitions/<id>/spec.yaml`)
  - leaderboard outputs:
    - root: `LEADERBOARD.md`, `LEADERBOARD.html` (committed snapshot for GitHub UI)
    - under `results/`: `results/leaderboard.json`, `results/leaderboard.csv`, `results/leaderboard.html`

### Next (ordered)
1) Kilo CLI capability spike:
   - verify whether Kilo can be run headlessly (no VSCode) against a workspace directory
   - confirm how to supply prompt deterministically
   - confirm what artifacts are available (stdout/stderr, transcript, structured JSON if any)
   - confirm we can enforce a hard wall-clock timeout (kill process) reliably
2) If the spike is a “go”, implement Phase 3 automation:
   - `python -m orchestrator.run_one auto ...` (headless run → validate → score → record → leaderboards)
   - `python -m orchestrator.sweep ...` for batching over model configs
3) If the spike is a “no-go”, revise Phase 3 before implementing sweeps (fallback options are listed in `docs/plan/v3.md`).

### Open questions
- Kilo CLI: can we reliably run headlessly, pass prompt/workspace, and capture a transcript/structured output?
- If Kilo CLI is not workable, what is the fallback automation approach for Phase 3?

## Known issues / current breakage
- None known.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
