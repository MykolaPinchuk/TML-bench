# HANDOFF

## Current slice
v5 (Phase 5): multi-competition benchmark runner (“one command”) + budget tiers (incl. SOTA 20m).

Latest decision (important): baseline prompt family is the default; time-gated and budget-aware are experimental.
- Decision record: `docs/adr/0003-default-prompt-family-baseline.md`
- Evidence + results tables: `docs/experiments/prompt_family_comparison_v5_core.md`, `results/exp_promptfam_comparison_runs.csv`
- Repo-root snapshot for humans: `results.md`

Legacy root leaderboards were moved to `archive/leaderboards/2026-02-02/` and leaderboard generation is now opt-in (`--write-leaderboards`).

## Next slice (approved): v5.5 (Phase 5.5) — reduce noise + expand coverage

Goal: make results less noisy and broaden the benchmark before starting v6 (security) for the first paper draft.

Important (prompting clarity; avoid confusion):
- **Strategy 1 = `legacy1`:** render prompt as `prompts/strategies/legacy1/base_prompt.md` + `prompts/strategies/legacy1/competition_overrides/<id>.md` (no profile layer).
- **Strategy 2 = `profiled1`:** render prompt as `prompts/strategies/profiled1/base_prompt.md` + `prompts/strategies/profiled1/prompt_profiles/<profile>.md` + `prompts/strategies/profiled1/competition_overrides/<id>.md`.
- `active` = the live prompt files under `prompts/` (may evolve).
- Select explicitly via `--prompt-strategy <id>` (supported by `orchestrator.run_one auto`, `orchestrator.sweep`, `orchestrator.suite`).
- `results.md` includes strategy-specific snapshots (working6 under both strategies; old5 under both strategies). Do not treat any tables as apples-to-apples unless the strategy id and replication/selection policy match.

Operational policy (current):
- Use **`profiled1`** as the default baseline strategy for routine runs and reporting.
- Use **`legacy1`** only for explicit robustness/sensitivity checks against the default.

Immediate plan for next agent (agreed with user):
- Expand model coverage by adding a few new candidate models (preflight first; keep only tool-capable/working entries).
- Keep all primary runs on **`--prompt-strategy profiled1`**.
- Run **`legacy1`** only when explicitly requested as a robustness check.
- Reduce noise by running **5 reps per cell** for the selected model set and reporting **median** as the primary statistic (with success-rate alongside).
- Update `results.md` and `HANDOFF.md` after each completed batch so strategy/comparability status stays explicit.

Current status (strategy comparison; v5.5):
- **working6 (6 models)** has controlled runs for both strategies (see `results.md` for the exact DBs and selection rules):
  - `legacy1`: 2 runs/cell for all 4 competitions (churn + remaining3 DB split).
  - `profiled1`: 2 reps/cell (rep1 + rep2).
- **old5 (`v3_fast.json`, 5 models)**:
  - `profiled1`: complete (2 runs/cell) in `results/results_v5_5_v3fast_profiled1_r2.sqlite`.
  - `legacy1`: complete (2 runs/cell) in `results/results_v5_5_v3fast_legacy1_r2.sqlite` (mode `v5_5_v3fast_legacy1_r2`) — apples-to-apples S1 vs S2 for old5 is now ready.

Operational note (avoid disk-full failures):
- Kilo stdout event logs are capped by default via `TML_KILO_STDOUT_MAX_BYTES` (documented in `README.md`).

Operational note (async reliability):
- Read `a2a_notes.md` before launching long runs.
- Use `python scripts/async_suite_runner.py start ...` for multi-hour suite batches so PID/log/status are durable and visible to the operator.

Scope:
- Add more models (split into a “main” tool-capable set vs “experimental” as needed).
- Add 1 more real competition (bringing the suite to 5 competitions; keep `toy_regression` as fixtures only).
- Increase replication (target `--runs-per-model 5`) and report medians to reduce variance/noise.
- Keep baseline prompt family as default; run experimental prompt profiles only by explicit override.
- Produce a fresh DB-backed run batch (new `--db-path`) and refresh:
  - `results.md` snapshot (committed)
  - optionally archive generated leaderboards under `archive/leaderboards/YYYY-MM-DD/` (opt-in via `--write-leaderboards`)

Exit criteria for v5.5:
- 5-competition suite file exists and runs end-to-end (at least `--dry-run` works with the updated suite/models).
- Expanded model set(s) exist and are referenced by the intended sweep/suite commands.
- “Less noisy” results are captured in a dedicated sqlite DB and summarized in `results.md`.

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
  - results / reporting:
    - repo-root summary: `results.md` (committed snapshot)
    - legacy leaderboards are archived under `archive/leaderboards/` (snapshots)
    - leaderboard generation is optional (off by default; use `--write-leaderboards` or `python -m orchestrator.leaderboard --write-root` when needed)
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
  - NanoGPT is retired as unreliable; any NanoGPT-specific model sets/artifacts are archival only.

- Leaderboard collision/variance visibility:
  - If generated, `LEADERBOARD.md` groups “Duplicate submissions” by `(budget_time_seconds, prompt_profile)` and includes a “Variance (per model/config)” table: `orchestrator/leaderboard.py`.
  - Secondary regression metric `r2` recorded as `secondary_r2` and surfaced in leaderboard outputs when present: `orchestrator/score.py`, `orchestrator/db.py`, `orchestrator/leaderboard.py`.

- Host baselines:
  - Deterministic sklearn baseline: `python scripts/run_baseline.py --competition-dir ... --baseline-type hgb`
  - Trivial constant baseline floor: `python scripts/run_baseline.py --competition-dir ... --baseline-type constant`
  - Baseline recording into DB (for absolute normalization across competitions):
    - `python -m orchestrator.baselines --competition-id <id>` records `hgb` + `constant` into `results/results.sqlite`.
    - If generated, `LEADERBOARD.md` “Overall” tables include `mean_abs_units` (0=constant, 1=hgb) and `beat_hgb_rate`.

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

- Monotonicity investigation (specs s-b/g-b/sota) + Chutes migration (agent06):
  - Suite + model sets used:
    - `orchestrator/suites/mono_chutes_churn_s6e1.json` (churn + ps-s6e1) (commit `192834b`)
    - `orchestrator/model_sets/chutes_mono_toolcapable_3.json` (commit `192834b`)
  - Replicated spec-as-is sweeps (3 runs/model/spec, `--concurrency 2`) to reduce noise:
    - s-b mode: `mono_chutes_suite_sb_rep3_20260131T200852Z`
    - g-b mode: `mono_chutes_suite_gb_rep3_20260131T210629Z`
    - sota mode: `mono_chutes_suite_sota_rep3_20260131T224713Z`
    - Experiment-scoped report: `tmp/mono_chutes_monotonicity_experiment.md` (local, untracked)
    - General report command:
      - `python -m orchestrator.spec_sanity --suite mono_chutes_churn_s6e1 --join-mode best --out-md tmp/mono_chutes_monotonicity_allbest.md`
  - Fixed-prompt control (budget-aware prompt at 240/600/1200) on churn:
    - Modes:
      - `mono_chutes_fixedprompt_churn_240_rep3_20260201T014957Z`
      - `mono_chutes_fixedprompt_churn_600_rep3_20260201T022624Z`
      - `mono_chutes_fixedprompt_churn_1200_rep3_20260201T030749Z`
    - Summary report with score medians: `tmp/mono_chutes_fixedprompt_churn_rep3_scores.md` (local, untracked)
  - Chutes stability smoke model set: `orchestrator/model_sets/chutes_smoke_2.json` (commit `192834b`)

- Prompt profile policy update (guarded “reasoning phase”, agent06/agent07):
  - Time-gated variants exist as **experimental** profiles (not default):
    - `prompts/prompt_profiles/good-baseline-timegated.md`
    - `prompts/prompt_profiles/sota-xgb-timegated.md`
  - Baseline defaults have no time-gate:
    - `prompts/prompt_profiles/simple-baseline.md`
    - `prompts/prompt_profiles/good-baseline.md`
    - `prompts/prompt_profiles/sota-xgb.md`
  - Decision record: `docs/adr/0003-default-prompt-family-baseline.md`

### Next (ordered)
0) Use baseline prompt family as the default for new runs:
   - 240: `simple-baseline`
   - 600: `good-baseline`
   - 1200: `sota-xgb`
   - Decision record: `docs/adr/0003-default-prompt-family-baseline.md`

1) If/when experimenting with prompt-policy changes again:
   - Use the standardized reporting artifacts:
     - `scripts/report_prompt_families_v5_core.py` (writes `docs/experiments/prompt_family_comparison_v5_core.md`)
   - Always report reliability + monotonicity (see `docs/plan/selection_protocol.md`).

2) Optional cleanup for future convenience:
   - Remove old baseline worktree under `tmp/worktrees/` if it’s no longer needed (it can interfere with `pytest` without `pytest.ini`).
   - **Models (5):** the Chutes entries in `orchestrator/model_sets/v3_fast.json`
     - `deepseek-ai/DeepSeek-V3.1-Terminus`
     - `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`
     - `zai-org/GLM-4.6-FP8`
     - `meta-llama/Meta-Llama-3.1-8B-Instruct`
     - `microsoft/Phi-3.5-mini-instruct`
   - **Specs/budgets:** 240 / 600 / 1200 seconds
   - **Execution knobs:** `--runs-per-model 1`, `--concurrency 2`
   - **Prompt families to compare (3):**
     - **Baseline:** `--prompt-strategy profiled1` with `--prompt-profile` set to:
       - 240: `simple-baseline`
       - 600: `good-baseline`
       - 1200: `sota-xgb`
     - **Time-gated (experimental):** `good-baseline-timegated` (600) and `sota-xgb-timegated` (1200) (freeze into a new prompt strategy id before treating results as stable).
     - **Budget-aware:** `prompt_profile=budget-aware` on 240/600/1200 (existing results are incomplete → rerun for the full suite + 5 models).
   - **DB hygiene (avoid mixing):** write each family into its own DB path under `results/` (do not reuse `results/results.sqlite` for new comparisons).

1) Validate whether the new “reasoning gate” improves outcomes without increasing `no submission.csv` failures:
   - Suggested A/B: churn and/or ps-s6e1, `--runs-per-model 3`, compare `--profile good-baseline` vs `--profile sota-xgb`.
2) Decide how to “answer monotonicity” formally:
   - Current evidence suggests strict monotonicity is not guaranteed per model even with replication.
   - Consider reporting capability (median/best-of-successes) separately from reliability (success rate).
3) Provider rationalization:
   - NanoGPT is retired and should not be used going forward (see Known issues + `tmp/nanogpt_402_debug/` for archived debug).
4) Publishable artifact packaging + anti-leak posture (defer to v6):
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
- Some provider-hosted models appear to support completions but fail to use Kilo tool-calling in headless mode (no `ask: command`), leading to `timeout: no submission.csv produced`.
- NanoGPT is retired (unreliable in headless Kilo runs; repeated `402 status code (no body)`); debug bundle remains under `tmp/nanogpt_402_debug/` (local, untracked).
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
  - Recent agent06 checkpoints:
    - `192834b` checkpoint(orchestrator): Chutes mono sweeps + leaderboards
    - `ca9e7e5` checkpoint(orchestrator): refresh leaderboards after rep sweeps
    - `21d03fd` checkpoint(prompts): add 6min reasoning gate
