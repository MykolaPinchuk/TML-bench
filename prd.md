# PRD: Tabular ML-Agent Benchmark and Leaderboard (Kilo + OSS Models)

## 1) Background and motivation

Modern “coding agents” can produce strong Kaggle-style tabular baselines quickly when run inside an IDE with the right context and local tooling. However:

* Existing agent benchmarks often focus on code correctness or synthetic tasks, not end-to-end tabular DS work (data loading, preprocessing, model training, submission formatting, iteration).
* Existing Kaggle-like benchmarks (e.g., MLE-bench) are broad and expensive, vary in scaffolding, and are harder to reproduce cheaply for repeated runs.
* Most of existing DS/ML benchmarks are not contamination-proof.
* For OSS models, there is no widely trusted, reproducible, budget-controlled leaderboard that measures: “Given a fixed scaffold, no web access, and a fixed runtime, how well does an autonomous agent solve a recent tabular Kaggle-style task?”

This project builds a **small, strict, reproducible, tabular-only benchmark** that can be run repeatedly across OSS models using a single universal scaffold: **Kilo Code**.

The intended use is both practical (choose models/settings for autonomous tabular DS work) and research-facing (evaluate agent capability under controlled conditions).

---

## 2) Objective and target state (Phase 6)

### Target state summary

A fully automated system that, given:

* a set of ~5 selected recent tabular competitions/tasks,
* a list of models (via Chutes or NanoGPT APIs),
* and an evaluation configuration (budgets, seeds, runs-per-model),

will execute autonomous agent runs end-to-end and produce:

* **per-run artifacts** (logs, code snapshots, submissions),
* **validated local scores** on a **private holdout set** inaccessible to the agent,
* **aggregated statistics** (success rate, mean/best score, variance),
* and a **leaderboard** (static HTML + machine-readable JSON/CSV).

### Key properties of the target state

1. **Universal scaffold**: all models run in the same Kilo-based harness.
2. **No web search**: agent containers have no general internet; egress allowlist only to the LLM API endpoints (because remote inference is required). (Enforced in Phase 6; best-effort policy before then.)
3. **Private holdout scoring**: labels and scoring code are not mounted into the agent environment.
4. **Low compute**: only tabular tasks; few competitions; fixed time budgets; repeatable runs.
5. **Auditable and reproducible**: pinned environments, deterministic splits, full artifacts retained.
6. **No contamination. Post-knowledge cutoff data/competitions.

---

## 3) Goals

### G1. Produce a credible leaderboard for OSS models on tabular DS-agent tasks

* Measure **score** and **success rate** under standardized conditions.
* Provide multiple runs per model to estimate variance.

### G2. Fully automate the pipeline (Phase 5)

* One command triggers full sweep across models × competitions × seeds.
* Output is a leaderboard plus run artifacts.

### G3. Keep it cheap and repeatable

* Small set of tasks (initially ~1, then expand to 5).
* Time-bounded runs.
* Minimal GPU dependence (CPU-first; optional GPU-enabled variant later).

### G4. Provide strong operational hygiene

* Containers for isolation.
* Strict egress.
* Deterministic splits and version pinning.
* Structured logs and artifacts.

---

## 4) Non-goals

* Not attempting to replicate the true Kaggle private leaderboard.
* Not supporting arbitrary Kaggle competitions at scale (initially only a curated handful).
* Not optimizing for interactive use; primary mode is batch evaluation.
* Not building a general multi-agent orchestration platform; scope is benchmark execution and scoring.

---

## 5) Assumptions and constraints

### A1. “Contamination-proof enough”

The working assumption is:

* choose competitions/tasks that are new relative to model release/cutoff,
* disable internet browsing for the agent,
* keep holdout labels inaccessible,
* run local scoring.

This is treated as adequate for your intended benchmark (no further contamination research required in v1).

### A2. Remote LLM inference required

The “no internet” constraint cannot be absolute because the agent must call model APIs. The real requirement is:

* **no general internet access**; only allowlisted egress to the LLM provider endpoint(s).

### A3. Kaggle data licensing / redistribution

If Kaggle competitions are used as the data source:

* do not redistribute competition datasets in the repo;
* provide scripts/specs that download data via Kaggle API and generate splits locally.
  (If later you want frictionless public usage, switch to datasets you can legally host.)

### A4. Kilo Code is the standardized scaffold

Kilo CLI must be used in **autonomous mode** and produce **machine-readable logs** for automation. Kilo CLI supports autonomous mode and JSON output (`--auto`, `--json`). ([Kilo][1])
Kilo CLI also supports MCP servers, which must be disabled or strictly controlled for benchmark integrity. ([Kilo][2])

---

## 6) Users and use cases

### Primary user

You (benchmark owner/operator), plus later external users who want to compare OSS models.

### Core use cases

* **UC1**: Run a single model on a single task once; get score and artifacts.
* **UC2**: Run a single model N times on a single task; estimate variance and success rate.
* **UC3**: Run M models across K tasks with fixed budgets; generate leaderboard.
* **UC4**: Debug failures via full logs, code snapshots, and reproducible re-run.

---

## 7) Benchmark definition

### 7.1 Unit of evaluation: a “Run”

A Run is identified by:

* `competition_id`
* `model_id` + `provider` + config (temperature, max_tokens, etc.)
* `seed` (split seed and/or run seed)
* `budget` (time limit; optional step/tool limits)
* `scaffold_version` (Kilo version + config hash)
* `env_version` (Docker image hash)

Run output:

* `submission.csv` (required for success)
* logs + transcript
* optional code snapshot / workspace tarball
* local holdout score

### 7.2 Success criteria

A run is successful if:

1. `submission.csv` exists.
2. Submission schema matches `sample_submission.csv`:

   * required columns present
   * row count matches `test_public.csv`
3. Values pass basic sanity checks (no NaNs unless explicitly allowed, correct dtypes if required).
4. Scoring completes without error and yields a numeric metric.

### 7.3 Metrics tracked

Per run:

* `status`: success | invalid_submission | runtime_error | timeout | other
* `score_raw`: metric as computed (e.g., RMSE, AUC, logloss)
* `score_normalized`: transformed so higher-is-better for leaderboard (e.g., `-RMSE`)
* `runtime_seconds`
* `attempt_count` (optional, if inferred from logs)
* `artifact_hashes` (for integrity)

Aggregated per (model, competition):

* `success_rate`
* `mean_score`, `median_score`, `std_score`
* `best_score`
* confidence intervals (bootstrap or t-interval; choose one and standardize)

---

## 8) Task/competition selection criteria

### Initial constraints

* Tabular only (no images/text heavy feature extraction).
* Reasonable dataset size (fits local training quickly).
* Clear metric and submission format.
* Minimal leakage traps; or if present, documented.

### Diversity across ~5 tasks (recommended)

* classification (AUC/logloss)
* regression (RMSE/MAE)
* mix of categorical-heavy and numeric-heavy
* one time-like split scenario (optional)

### Packaging requirement

For each competition/task, the benchmark will create:

* **public agent-visible files**: `train_public.csv`, `test_public.csv`, `sample_submission.csv`, `README_task.md`
* **private files**: holdout labels and authoritative scoring code

---

## 9) Data and scoring protocol (private holdout)

### 9.1 Split generation (deterministic)

Given original Kaggle `train.csv` with labels:

* produce `train_public.csv`: subset of rows with labels (agent sees labels here)
* produce `test_public.csv`: holdout features only (labels removed)
* store holdout labels privately (outside agent environment)

Split strategies:

* default: random split with fixed seed
* classification: stratified split
* group/time-based: optional, if task requires it (explicit in `spec.yaml`)

Store the split mapping (row ids) and seed under `private/`.

### 9.2 Scoring

Scoring is performed outside the agent container using private labels:

* `score_submission(submission.csv, y_holdout_private, metric)` → scalar score

Important: the scoring code and holdout labels are never accessible to the agent container.

### 9.3 Candidate submissions + selection vs evaluation (diagnostic protocol)

Problem observed in Phase 5: with larger budgets, agents often explore more and can end a run by leaving a **worse final** `submission.csv` even if a better submission existed earlier in the run. This breaks the intuitive expectation that more budget should help.

To diagnose this cleanly (without leaking the evaluation holdout), we use a **two-holdout protocol**:

1. **Agent-generated candidates (no oracle):**
   - During a run, the agent writes multiple candidate submissions, e.g. `submissions/sub_001.csv`, `submissions/sub_002.csv`, …
   - The agent writes a machine-readable `submissions/summary.json` including:
     - list of candidates + filenames,
     - local validation score(s) and CV scheme,
     - a short note of what changed,
     - and which candidate the agent selected as the final `submission.csv`.

2. **Selection holdout (private, not evaluation):**
   - In addition to the final evaluation holdout, maintain a separate **selection holdout** that is also hidden from the agent.
   - The harness scores *all* valid candidates on the selection holdout and picks the best candidate (`oracle_selected_submission`).
   - This is used only to measure whether the agent *could* have selected a better candidate if it had perfect-but-non-eval feedback.

3. **Evaluation holdout (official leaderboard):**
   - The official leaderboard remains the score of the agent’s final `submission.csv` on the evaluation holdout.
   - Optionally (for debugging only), also compute the evaluation-holdout score of `oracle_selected_submission` to quantify “selection regret”.

Interpretation:
- If selection-holdout best improves with budget but agent’s final does not: the issue is mostly **selection** (agent can generate better candidates but fails to pick them).
- If neither improves: the issue is mostly **search/modeling** (extra time is not producing better candidates).
- If selection holdout improvements do not translate to evaluation holdout: splits are misaligned or agents are overfitting to spurious patterns.

Guardrails:
- Cap the number of candidates per run (or dedupe by normalized submission hash) so “more time → more candidates → mechanically better best-of-K” is explicit and controlled.
- Treat “oracle-selected best” as a diagnostic metric, not the primary leaderboard metric.

---

## 10) System architecture

### 10.1 High-level components

1. **Competition Registry**

   * Directory of competition specs and scripts
   * Responsible for generating public/private artifacts from Kaggle downloads

2. **Orchestrator**

   * Creates run workspaces
   * Launches Kilo agent runs
   * Validates outputs
   * Calls scorer
   * Records results

3. **Agent Runner (Kilo CLI)**

   * Runs inside the agent container (Phase 4+)
   * Autonomous mode
   * Produces logs and artifacts

4. **Validator**

   * Ensures submission correctness

5. **Scorer**

   * Runs in trusted environment (host or separate service)
   * Reads private holdout labels
   * Computes metric

6. **Results Store**

   * SQLite/Postgres initially
   * Stores run metadata and scores

7. **Leaderboard Builder**

   * Aggregates results
   * Outputs static HTML + JSON/CSV

### 10.2 Trust boundaries

* **Untrusted**: agent container filesystem + execution
* **Trusted**: orchestrator + scorer + private data directory

Note: in Phases 1–5, this “untrusted vs trusted” boundary is primarily by convention and workflow (best-effort). Hard enforcement (mount isolation + egress restrictions) is introduced in Phase 6.

Mount policy (Phase 4+):

* `public/` mounted read-only into container
* `work/` mounted read-write into container
* `private/` NOT mounted

### 10.3 Network policy

Target (Phase 6): deny all outbound traffic from the agent container except allowlist to:

* Chutes base URL `https://llm.chutes.ai/v1/` (OpenAI-compatible), if using Chutes proxy ([LiteLLM][3])
* NanoGPT base URL `https://nano-gpt.com/api/v1` (OpenAI-compatible), if using NanoGPT ([LiteLLM][4])

Before Phase 6: enforce “no web search / no retrieval” via prompt policy and run workflow, but treat results as non-secure.

---

## 11) Kilo integration requirements

### 11.1 Kilo CLI execution mode

* Must run in autonomous mode so orchestrator can treat it as a batch job.
* Must emit structured output for parsing and auditing.

Kilo CLI supports:

* `--auto` autonomous mode (no user interaction)
* `--json` structured output mode (used with `--auto`) ([Kilo][1])

### 11.2 Disable/lock down MCP and other “side channels”

Kilo CLI supports MCP via separate CLI config paths. ([Kilo][2])
Benchmark policy:

* MCP disabled by default.
* If later enabled, only allow a local, non-network MCP server with fixed behavior (and document it in benchmark version).
* Hard enforcement (container + config lockdown) is a Phase 6 requirement; earlier phases rely on configuration and prompt policy.

### 11.3 Standardized prompt template

A single prompt template must be used for all models/runs per task, parameterized only by:

* dataset paths
* target column name
* metric definition
* time budget
* required output filename and schema

Prompt policy:

* Explicitly require: “write `submission.csv` in the exact format of `sample_submission.csv`”
* Explicitly require: “print local validation score on a split of train_public”
* Explicitly require: “do not use web; do not attempt retrieval”

---

## 12) Provider integration (Chutes and NanoGPT)

### 12.1 OpenAI-compatible routing

Both providers support OpenAI-compatible APIs:

* Chutes (OpenAI-compatible endpoints; base URL commonly `https://llm.chutes.ai/v1/`). ([LiteLLM][3])
* NanoGPT (base URL `https://nano-gpt.com/api/v1`; OpenAI-compatible behavior). ([LiteLLM][4])

Implementation approach:

* Configure Kilo to use an OpenAI-compatible provider with:

  * `base_url`
  * `api_key`
  * `model` name string
* The orchestrator injects these per run via environment variables or per-run config files.

### 12.2 Quota scaling

Treat quotas as an operational parameter; no special design dependency other than:

* backoff/retry handling
* rate limiting at orchestrator level
* per-run request cap optional (to avoid runaway costs)
* for Chutes + NanoGPT (subscription-based, high daily included limits), assume cost is not the binding constraint; optimize for iteration speed instead

---

## 13) Repository and configuration layout (proposed)

```
tabular-agent-bench/
  README.md
  LICENSE
  docs/
    PRD.md
    BENCHMARK_PROTOCOL.md
    REPRODUCIBILITY.md
  competitions/
    <comp_id>/
      spec.yaml
      prepare_competition.py
      public_template/
        README_task.md
      private/            # local-only, gitignored
      public/             # generated, gitignored or cached
  prompts/
    base_prompt.md
    competition_overrides/
      <comp_id>.md
  env/
    docker/
      Dockerfile
      requirements.lock
      kilo_config/
        settings.json
        mcp_settings.json  # disabled by default
  orchestrator/
    run_one.py
    sweep.py
    validate.py
    score.py
    db.py
    leaderboard.py
    schemas.py
  runs/                   # generated
    <run_id>/
      workspace/
      artifacts/
      result.json
  results/
    results.sqlite
    leaderboard.json
    leaderboard.html
```

Policy: `competitions/*/private` and generated data are not committed.

---

## 14) Interfaces and data contracts

### 14.1 `spec.yaml` (per competition)

Minimum fields:

```yaml
id: playground-series-s6e1
task_type: regression   # regression|binary|multiclass
target_column: exam_score
metric:
  name: rmse
  higher_is_better: false
submission:
  filename: submission.csv
  id_column: id
  prediction_column: exam_score
split:
  strategy: random      # random|stratified|group|time
  test_size: 0.2
  seed: 1337
budgets:
  time_seconds: 900
env:
  python: "3.11"
  allow_gpu: false
```

### 14.2 Run result record (`result.json`)

```json
{
  "run_id": "...",
  "competition_id": "...",
  "model": {"provider": "chutes", "model_id": "...", "temperature": 0.2},
  "seed": 123,
  "budget": {"time_seconds": 900},
  "status": "success",
  "score_raw": 0.5123,
  "score_normalized": -0.5123,
  "runtime_seconds": 847,
  "artifacts": {
    "submission_path": "artifacts/submission.csv",
    "kilo_transcript_path": "artifacts/kilo.json"
  },
  "versions": {
    "docker_image": "sha256:...",
    "kilo": "0.x.y",
    "benchmark": "v1.0.0"
  }
}
```

---

## 15) Integrity and anti-cheat controls (v1)

Controls enforced by system design:

* No general internet egress from agent container (allowlist only to LLM endpoint).
* Holdout labels and scorer not mounted into agent container.
* Prompt explicitly forbids retrieval and external resources.

Controls for auditing:

* Store full Kilo JSON transcript.
* Store full stdout/stderr.
* Optionally run static checks on workspace to detect presence of forbidden binaries/scripts.

(Plagiarism detection and code similarity checks are optional in v1; add later if needed.)

---

## 16) Implementation plan (phased, iterative)

You have Phase 0 completed: interactive POC in Kilo VSCode extension with data already present.

### Phase 1 — Reproducible scoring + validation (no agent automation, no Docker)

**Goal:** lock down the evaluation logic first.

Deliverables:

* `prepare_competition.py` for one selected competition:

  * downloads data (outside benchmark or via script)
  * generates deterministic split
  * writes `train_public.csv`, `test_public.csv`, private labels
* `validate.py`: schema/rowcount checks vs `sample_submission.csv`
* `score.py`: metric computation using private labels
* `BENCHMARK_PROTOCOL.md`: defines success criteria and metrics.

Acceptance criteria:

* Given any `submission.csv`, validation and scoring work deterministically.
* Holdout labels are not present in agent-visible directories.

### Phase 2 — VSCode-based harness wrapper (semi-automated runs)

**Goal:** get repeated runs + leaderboard while still using VSCode manually for execution (functionality only; not secure).

Execution mode:

* Use Kilo VSCode agent optionally for interactive iteration/debugging.
* Use per-run workspaces (`runs/<run_id>/workspace/`) that include only `public/` inputs plus an empty `work/` area for outputs.
* Enforce constraints “politely” (prompt policy + workflow discipline), not via isolation.

Deliverables:

* `runs/` workspace templating + `run_id` creation script
* `record_result.py` appends to `results.sqlite`
* `leaderboard.py` prints a stable summary table.

Acceptance criteria:

* You can execute N runs (manual trigger), then generate leaderboard from stored results.

### Phase 3 — Kilo CLI batch execution on host (no Docker)

**Goal:** replace VSCode UI with Kilo CLI to make full batch possible (functionality only; not secure).

Important note:

* The exact Kilo CLI interface and its ability to run headlessly is **unverified** at the time of writing.
* Phase 3 must start with a short “CLI capability spike” to confirm the invocation, how to pass a prompt/workspace, and how to capture structured outputs/transcripts.
* If Kilo CLI is not workable/stable, Phase 3 deliverables must be revised (e.g., keep Phase 2 manual runs for longer, or use an alternative automation harness) before building a large sweep system.

Deliverables:

* CLI capability spike:
  * document the working Kilo CLI invocation (or lack of it) and what artifacts are available (JSON transcript, logs, exit codes).
  * confirm how to enforce a wall-clock timeout (process kill) reliably.
* `run_one.py` drives Kilo CLI (headless) and captures structured output/transcript **if** supported.
* `sweep.py` loops over seeds and runs-per-model.
* Backoff/retry for transient API errors.
* Wall-clock timeout enforcement per run.

Acceptance criteria:

* A single command performs: run → validate → score → record.
* Repeatability across runs is stable.

### Phase 4 — Reproducibility packaging + baselines

**Goal:** reduce drift and improve debuggability without attempting security.

Deliverables:

* Pinned dependencies (lockfile) and pinned Kilo version.
* Baseline runner per competition (non-agent) to sanity-check data/scoring.
* Stronger provenance capture (at least):
  * spec hash
  * rendered prompt hash (base + override + parameters)
  * public data manifest hashes
  * Kilo version + config hash (or equivalent)
  * model identity fields (provider, model_id, mode, temperature, max_tokens)

Acceptance criteria:

* Same run config produces comparable results across machines (within expected variance).
* Baseline achieves stable, reproducible scores for each competition.

### Phase 5 — Multi-competition benchmark + public leaderboard artifact

**Goal:** full benchmark (5 tasks), model sweep, publishable output (results still non-secure until Phase 6).

Deliverables:

* `competitions/` registry with 5 tasks and documented selection rationale.
* A model-centric leaderboard artifact generated from DB (at minimum per-competition best-by-model):
  * `leaderboard.html`
  * `leaderboard.json`
* `REPRODUCIBILITY.md` with exact rerun instructions and version pins.
* Versioning scheme for benchmark releases (v1, v1.1, etc.).

Acceptance criteria:

* One command produces the full leaderboard deterministically given the same inputs and model APIs.
* All artifacts required to audit any score are retained.

### Phase 6 — Security hardening (isolation + strict rules)

**Goal:** enforce benchmark integrity controls so results can be treated as security-relevant.

Deliverables:

* Docker isolation with strict mounts (`public/` ro, `work/` rw, `private/` not mounted).
* Egress allowlist (deny all outbound except model API endpoints).
* Locked-down Kilo configuration (MCP disabled; no side-channel tools).
* Resource limits (CPU/RAM/disk) and explicit network/egress tests.

Acceptance criteria:

* Agent cannot read private holdout labels (verified by mount layout tests).
* Agent has no general internet access (verified by network policy tests).
* The same run config produces comparable results across machines (within expected variance).

---

## 17) Testing strategy

### Unit tests

* split generation determinism
* metric computation correctness (known small fixtures)
* submission validator

### Integration tests

* “dummy agent” that writes a simple baseline submission
* orchestrator run lifecycle: create workspace → run → validate → score → record

### End-to-end tests

* one real model, one competition, one run
* one real model, one competition, N runs

---

## 18) Operational considerations

### Run budgets and guardrails

* default: fixed wall-clock timeout per run
* optional: max training iterations, max file sizes, max disk usage
* enforce CPU/RAM limits per container

### Artifact retention policy

Minimum per run:

* `submission.csv`
* Kilo transcript (`--json` output)
* stdout/stderr
* `result.json` record
  Optional:
* entire workspace tarball (for deep debugging)

### Failure taxonomy

Standardize error categories for reporting:

* timeout
* invalid submission schema
* runtime exception
* OOM/resource limit
* API error / rate limit

---

## 19) Publication/release posture (when you choose to publish)

To be publishable as a benchmark:

* Provide a stable benchmark version pin (competition specs + splits + env hash + Kilo config hash).
* Provide clear protocol doc + reproducibility instructions.
* Provide baseline references (simple sklearn model) for each task.
* Avoid distributing Kaggle datasets; ship download/split scripts and document required user actions (Kaggle API token + rules acceptance).

---

## 20) Open decisions to resolve early (for the Architect Agent)

1. **Holdout split style**: random vs stratified vs time/group for each of the 5 tasks.
2. **Budget definition**: single time budget per run, or per-task budgets.
3. **Model configuration**: fixed temperature across all models, or per-model tuning allowed (recommended: fixed).
4. **Leaderboard aggregation**: mean-of-N vs best-of-N vs both (recommended: report both, but rank by mean).
5. **Result normalization**: how to map different metrics into a consistent “higher is better” score.

---

## 21) Immediate next step (what the Architect Agent should do)

Design the codebase and low-level implementation plan for **Phase 1 → Phase 3** first (no Docker), because:

* it validates the core scoring/validation protocol,
* it proves Kilo CLI batchability,
* it yields a working leaderboard quickly.

Then extend to Phase 4 (Docker + network policy) once the end-to-end host pipeline is stable.

[1]: https://kilo.ai/docs/cli?utm_source=chatgpt.com "Kilo Code CLI | Kilo Code Docs"
[2]: https://kilo.ai/docs/features/mcp/using-mcp-in-cli?utm_source=chatgpt.com "Using MCP in the CLI"
[3]: https://docs.litellm.ai/docs/providers/chutes?utm_source=chatgpt.com "Chutes"
[4]: https://docs.litellm.ai/docs/providers/nano-gpt?utm_source=chatgpt.com "NanoGPT"
