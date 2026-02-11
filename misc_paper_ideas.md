# misc_paper_ideas.md

Brainstorm notes for the first paper draft.
Status: exploratory, not a locked plan.

## 1) Possible paper value propositions

1. Evaluation methodology contribution:
- Show why single-run agent benchmarks are unstable.
- Propose a practical reliability-aware protocol (`n=5` per cell + median + success-rate sidecar).

2. Reliability as first-class metric:
- Demonstrate that "high score on one run" can be less useful than "slightly lower score with high completion rate".

3. Budget-response characterization:
- Measure how model performance changes from 240s -> 600s -> 1200s.
- Show that budget gains are model-dependent and sometimes non-monotonic.

4. Cross-task robustness:
- Separate "specialists" (win single tasks) from "generalists" (stable across competitions).

5. Operational reproducibility:
- Present logging/postmortem workflow as part of benchmark design (not an afterthought).


## 2) Candidate results to show in v1

1. Main tables:
- Per competition x spec ranking using median score over 5 successful runs.

2. Reliability panels:
- Success/timeout/runtime_error/provider_error rates by model x spec x competition.

3. Variance panels:
- IQR/range over the 5 runs per cell.

4. Budget scaling plots:
- Per-model delta from 240 -> 600 and 600 -> 1200.

5. Reliability-adjusted ranking:
- A score adjusted by completion probability (or show score + reliability jointly as a Pareto front).

6. Failure taxonomy:
- Most common failure classes and where they concentrate.


## 3) Hypotheses worth testing

1. H1: `n=5 + median` changes ranking stability materially vs single-run ranking.
2. H2: Higher budget improves median performance on average, but effect size varies by model and task.
3. H3: Reliability and score are only partially correlated; both are needed to assess utility.
4. H4: Some models are low-budget efficient; others need high budgets to become competitive.
5. H5: Cross-competition ranking differs from single-competition ranking (generalization gap).
6. H6: Failure mode profile is model-specific and can predict practical throughput.


## 4) "Far-fetched but interesting" ideas

1. Portfolio policy:
- Route each (competition, spec) to a different model to optimize expected score under a fixed wall-clock budget.

2. Early-abort controller:
- Use first 60-90s telemetry to decide continue/restart/switch model.

3. Benchmark-quality metric:
- Quantify quality of evaluation setups themselves (stability, observability, reproducibility).

4. Time-series drift study:
- Repeat monthly and track whether model updates improve score, reliability, or both.

5. Resilience stress test:
- Controlled faults (provider blips, tighter budgets) to compare robustness of models and orchestration.


## 5) Telemetry audit: what we already record

Useful data already captured per run (result.json + sqlite):
- identifiers: `run_id`, `competition_id`, `provider`, `model_id`, `mode`
- outcome: `status` (`success`, `timeout`, `runtime_error`, `invalid_submission`, `provider_error`, ...)
- metrics: `score_raw`, `score_normalized`, `metric_name`, `secondary_r2` (when available)
- timing: `runtime_seconds`, `budget_time_seconds`
- prompt/runtime config: `prompt_profile`, `prompt_strategy`, `seed`
- provenance/version: prompt/spec/public-manifest hashes, git sha/dirty, kilo version/config hash
- headless artifacts summary in notes: kilo return code, timeout, stage metadata, cleaned event count
- raw artifacts per run: `kilo_stdout*.jsonl`, `kilo_stderr.log`, `kilo_run.json`

Useful data already captured for long async batches:
- async `status.json`, `events.jsonl`, postmortem, and systemd diagnostic fields.


## 6) Gaps that matter for paper questions

1. No first-class "failure reason code" column in sqlite (beyond coarse `status`).
2. No first-class "time-to-first-valid-submission" metric.
3. No structured per-run tool-call/command counts in sqlite.
4. No standardized token/cost accounting in sqlite (even if present in raw events).
5. No first-class memory/CPU peak per run in sqlite (only available from systemd/journal for async jobs).


## 7) What to start recording now (high priority)

1. Stable failure taxonomy sidecar:
- Generate/store a per-run CSV with normalized failure reason labels:
  - `tool_not_used`, `provider_402`, `timeout_no_submission`, `oom_kill`, `invalid_submission`, etc.
- Keep mapping rules versioned.

2. Run telemetry sidecar (derived from `kilo_stdout.clean.jsonl`):
- `tool_call_count`, `command_count`, `first_tool_ts`, `first_submission_ts`, `api_error_count`.
- If usage data exists in events: `prompt_tokens`, `completion_tokens`, `estimated_cost`.

3. Time-to-first-valid-submission:
- Derive during/after run and store in sidecar (and eventually sqlite).

4. Batch resource summary:
- Persist run-level `MemoryPeak`, `MemorySwapPeak`, `CPUUsageNSec` from systemd for async runs.

5. Analysis snapshot export after each major batch:
- Freeze a denormalized per-run CSV for the paper (so draft figures remain reproducible even as DB evolves).


## 8) Minimal v1 recommendation

For first draft, do not block on perfect telemetry.
Prioritize:
1. `n=5` completion with medians.
2. Success-rate + failure breakdown.
3. Budget scaling and variance.
4. A short methodology section explaining observability and postmortem policy.
