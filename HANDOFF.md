# HANDOFF

## Current slice
v4 (Phase 4): reproducibility packaging + baselines (reduce drift; improve auditability; no security yet).

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
- Phase 3 headless batch execution (no Docker; functionality-only):
  - Kilo CLI runner: `orchestrator/kilo_cli.py` (headless `kilo --auto --json ...` with cleaned JSONL)
  - End-to-end headless run: `python -m orchestrator.run_one auto ...` (run → validate → score → record → leaderboards)
  - Batch sweep runner: `python -m orchestrator.sweep ...` (supports `--concurrency` without sqlite contention)
  - Provider setup helper (no secrets in git): `scripts/setup_kilo_providers.py` reading `secrets/provider_apis.txt`
  - Audit trail:
    - per-run Kilo JSON event logs under `runs/<run_id>/artifacts/kilo_stdout*.jsonl`
    - `runs/<run_id>/artifacts/kilo_run.json` and `result.json` notes with submission hashes

### Next (ordered)
1) Phase 4 reproducibility packaging:
   - pin Python dependencies (lockfile) and pin Kilo version in docs
   - capture stronger provenance per run:
     - spec hash
     - rendered prompt hash (base + override + params)
     - public data manifest hashes
     - Kilo version + selected provider config hash (redacted; no secrets)
2) Separate “non-agent baseline” from “agent runs”:
   - keep a deterministic host baseline per competition (sanity)
   - remove baseline injection for leaderboard sweeps (keep only as optional smoke/debug mode)
3) Documentation improvements for rerunability:
   - `REPRODUCIBILITY.md` with exact steps (incl. provider setup script, required env, pins)
   - clarify what artifacts are expected for audit (run dirs, logs, hashes, leaderboard rebuild command)

### Open questions
- Provider attribution: Kilo’s JSON event stream may not clearly report the upstream endpoint/provider dashboards; decide what additional logging (without secrets) is acceptable/possible.
- Baseline policy: what is the default Phase 4 posture for sweeps (blank workspace vs seeded helper file) and time budget?

## Known issues / current breakage
- Provider dashboards may not reflect activity even when local Kilo logs show API events; treat local per-run artifacts as the current audit source-of-truth.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
