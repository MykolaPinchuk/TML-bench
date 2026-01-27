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

- Baseline policy + sweep reliability (v4):
  - Workspace baseline seeding removed entirely (no injected `train_model.py`).
  - Headless Kilo timeouts now kill the whole process group to avoid orphaned `python train_model.py` processes: `orchestrator/kilo_cli.py`.
  - Headless prompt profiles:
    - `simple-baseline` (240s): `python -m orchestrator.sweep --profile simple-baseline ...`
    - `good-baseline` (600s): `python -m orchestrator.sweep --profile good-baseline ...`
  - Default sweep parallelism: if >4 models selected, default `--concurrency 5` (else 4): `orchestrator/sweep.py`.
  - Per-run deterministic `seed` recorded (derived from `run_id`) to track within-model variance: `orchestrator/run_one.py`.

- Leaderboard collision/variance visibility:
  - Root `LEADERBOARD.md` groups “Duplicate submissions” by `(budget_time_seconds, prompt_profile)` and includes a “Variance (per model/config)” table: `orchestrator/leaderboard.py`.
  - Secondary regression metric `r2` recorded as `secondary_r2` and surfaced in leaderboard outputs when present: `orchestrator/score.py`, `orchestrator/db.py`, `orchestrator/leaderboard.py`.

- Host baselines:
  - Deterministic sklearn baseline: `python scripts/run_baseline.py --competition-dir ... --baseline-type hgb`
  - Trivial constant baseline floor: `python scripts/run_baseline.py --competition-dir ... --baseline-type constant`
  - Baseline recording into DB (for absolute normalization across competitions):
    - `python -m orchestrator.baselines --competition-id <id>` records `hgb` + `constant` into `results/results.sqlite`.
    - Root `LEADERBOARD.md` “Overall” tables include `mean_abs_units` (0=constant, 1=hgb) and `beat_hgb_rate`.

- Competition expansion (v4):
  - Added competition scaffolds:
    - `competitions/bank-customer-churn-ict-u-ai/` (binary AUC; target `Exited`)
    - `competitions/foot-traffic-wuerzburg-retail-forecasting-2-0/` (regression RMSE)
    - `competitions/playground-series-s5e10/` (regression RMSE; target `accident_risk`)
    - `competitions/predicting-road-accident-risk-buaa/` (scaffold; spec inferred on first `prepare_competition.py --download`; may require accepting rules)
  - Regenerated leaderboards including the new competitions:
    - latest committed leaderboard refresh: commit `9583af5`

### Next (ordered)
1) Expand competition coverage (so “Overall” is meaningful):
   - Prepare + baseline + sweep `playground-series-s5e10` and `predicting-road-accident-risk-buaa`, then add 1 more tabular competition (preferably classification) to get closer to the target ~5 tasks; ensure baselines exist (`hgb` + `constant`) so absolute normalization is populated.
2) Reduce `simple-baseline` failures (less about collisions now):
   - Consider provider/model-specific tweaks (timeout bump, retry-on-timeout) while keeping `simple-baseline` nominally 240s.
3) Baseline automation:
   - Optionally auto-record missing baselines (constant+hgb) when a competition is first used, so absolute normalization is always available.

### Open questions
- Provider attribution: Kilo’s JSON event stream may not clearly report the upstream endpoint/provider dashboards; decide what additional logging (without secrets) is acceptable/possible.
- Baseline posture: how aggressive should `simple-baseline` be about forcing diversity vs. maximizing success rate?

## Known issues / current breakage
- Provider dashboards may not reflect activity even when local Kilo logs show API events; treat local per-run artifacts as the current audit source-of-truth.
- `simple-baseline` sweeps can still show occasional timeouts (e.g., NanoGPT deepseek-v3.2 @240s).
- Some Kaggle competitions require accepting rules / entering before `kaggle competitions download` works (403). If a new competition download fails, enter via browser once, then rerun `prepare_competition.py --download`.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
