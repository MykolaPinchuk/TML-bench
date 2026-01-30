# HANDOFF

## Current slice
v5 (Phase 5): multi-competition benchmark runner (“one command”) + budget tiers (incl. SOTA 20m). Publishable artifact packaging is deferred until v6.

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

- Phase 5 runner + SOTA tier (v5):
  - Suite runner across the core 4 competitions: `python -m orchestrator.suite ...` (default suite at `orchestrator/suites/v5_core.json`).
  - SOTA tier profile (20 min, XGBoost allowed): `--profile sota-xgb` (1200s) on `orchestrator.sweep` / `orchestrator.run_one auto`.
  - Sweep resume support (DB-backed): `python -m orchestrator.sweep ... --resume` (skip already-recorded runs for the same budget/profile).
  - Headless fail-fast on provider errors: `orchestrator/kilo_cli.py` terminates early when `402 status code` is seen; recorded as `provider_error` by `orchestrator/run_one.py` (commit `df0ce18`).
  - Provider setup hardening: `scripts/setup_kilo_providers.py` aligns `~/.kilocode/cli/global/secrets.json` mode defaults to the selected provider to avoid startup calls going to the wrong gateway (commit `9f6cea8`).
  - NanoGPT “tool-capable” model set: `orchestrator/model_sets/nanogpt_toolcapable.json` (Qwen-only) because some NanoGPT-hosted models do not reliably emit tool calls in headless mode (commit `80ac7ec`).

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
  - Regenerated leaderboards including the new competitions:
    - latest committed leaderboard refresh: commit `9583af5`
  - Benchmark suite posture (v4 completion): **4 competitions** total (no further expansion in v4):
    - `bank-customer-churn-ict-u-ai`
    - `foot-traffic-wuerzburg-retail-forecasting-2-0`
    - `playground-series-s6e1`
    - `playground-series-s5e10`

### Next (ordered)
1) Phase 5 (v5): run the full suite end-to-end and refresh committed leaderboard snapshots:
   - `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile simple-baseline --runs-per-model N --resume`
   - If NanoGPT runs are flaky, prefer `orchestrator/model_sets/nanogpt_toolcapable.json` over the broader NanoGPT set.
2) Expand model sets (when ready):
   - Add/update `orchestrator/model_sets/*.json` for “SOTA” models and run them at `--profile sota-xgb` (1200s).
3) Publishable artifact packaging + anti-leak posture (defer to v6):
   - Timestamped “bundle” outputs and freshness-cutoff verification during `prepare_competition.py`.

### Future backlog / ideas (unprioritized)
- Add a provider “preflight” to `orchestrator.suite` / `orchestrator.sweep`:
  - quick auth check + tiny completion
  - quick tool-call check (e.g. `ls`) to detect `MODEL_NO_TOOLS_USED` before scheduling multi-minute runs.
- Add capability-aware model sets and/or metadata:
  - Some provider-hosted models narrate actions but fail to emit tool calls in Kilo headless mode (no `ask: command`), leading to `timeout: no submission.csv`.
  - Consider splitting model sets into “tool-capable” vs “experimental”, or adding fields like `supports_tools`, `notes`, etc.
- Improve failure classification + fast failure:
  - Detect and label `402`/credit failures, `MODEL_NO_TOOLS_USED`, and “unexpected API response (no assistant messages)” distinctly in results.
  - Avoid burning the full time budget when the provider is failing.
- Logging/auditing upgrades (space-aware):
  - Decide whether to retain full non-code assistant outputs (excluding generated code) in run artifacts, and/or add optional compression/rotation of Kilo JSONL logs.
  - Consider surfacing tokens/cost metadata (when present in Kilo JSON events) into `result.json` + leaderboard.
- Leaderboard enhancements:
  - Time-used fraction is useful; consider also surfacing tool-call counts, token usage (if available), and “success rate” summaries by `(provider, model_id, prompt_profile, budget)`.
  - Consider a “prompt revision” tag (in addition to `prompt_sha256`) to make apples-to-apples prompt comparisons easier.
- Prompt experiments / methodology:
  - If results seem contradictory (e.g., stronger models underperform after a prompt change), run A/B sweeps where only the prompt changes (same models, budgets, seeds) and compare success rates + scores.
  - Keep prompts free of ML technique hints; focus on time budget + reliability + “keep improving until budget”.
- Model pool expansion:
  - Add additional cheap models (while keeping costs bounded).
  - OpenRouter policy: do **not** use `google/gemini-2.5-flash`; only allow `x-ai/grok-4.1-fast` from OpenRouter.
- SOTA tier evolution:
  - If/when adding a 20-minute SOTA tier (already `--profile sota-xgb` = 1200s), consider a separate “SOTA-LLM” profile and/or explicit rerun cadence for top models.

### Open questions
- Provider attribution: Kilo’s JSON event stream may not clearly report the upstream endpoint/provider dashboards; decide what additional logging (without secrets) is acceptable/possible.
- Baseline posture: how aggressive should `simple-baseline` be about forcing diversity vs. maximizing success rate?

## Known issues / current breakage
- Provider dashboards may not reflect activity even when local Kilo logs show API events; treat local per-run artifacts as the current audit source-of-truth.
- Some provider-hosted models appear to support completions but fail to use Kilo tool-calling in headless mode (no `ask: command`), leading to `timeout: no submission.csv produced`. This is the main reason for the `nanogpt_toolcapable` model set.
- Some Kaggle competitions require accepting rules / entering before `kaggle competitions download` works (403). If a new competition download fails, enter via browser once, then rerun `prepare_competition.py --download`.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
- v5 initialization commits:
  - `b811a1b` and `7b98385` on local branch `v5` (workflow docs + log rotation).
- v5 progress commits:
  - Added SOTA tier plumbing + sweep resume + suite runner (see recent local commits on `v5`).
  - Recent v5 checkpoints worth knowing:
    - `df0ce18` fail fast on provider 402
    - `9f6cea8` setup: align kilo global secrets for headless runs
    - `80ac7ec` add nanogpt tool-capable model set
    - `fc6f669`/`7a2f545`/`374f389`/`ebbede6`/`f912a05` prompt reliability iterations (short output, robustness, fast baseline)
    - `63985de` checkpoint(results): reran NanoGPT Qwen across all 3 profiles and refreshed leaderboard snapshots
    - `a778e9c` future backlog/ideas documented
