# ADR 0003 — Default prompt family is baseline

## Context

This repo relies on prompt profiles (`prompts/prompt_profiles/*.md`) to guide the headless ML agent.

We explored two prompt-policy enhancements intended to make better use of longer budgets:

- **Time-gated**: after producing a valid submission and with ≥6 minutes remaining, spend up to ~3 minutes on structured reasoning (“think hard”) and then try to improve the model.
- **Budget-aware**: apply a single workflow policy across budgets, scaling effort as budget increases.

The expectation was that “more time ⇒ better score” would be more monotonic and/or that longer budgets would clearly help.
However, any such change is only useful if it preserves (or improves) **reliability** (i.e., the agent consistently produces a scorable submission).

To make a decision, we ran a controlled comparison on the Phase-5 suite runner.

## Experiment (what we actually ran)

Locked design:

- Suite: `orchestrator/suites/v5_core.json` (4 competitions)
- Provider: Chutes-only
- Models: 5 models from `orchestrator/model_sets/v3_fast.json`
- Budgets: 240 / 600 / 1200 seconds
- Execution: `--runs-per-model 1`, `--concurrency 2`

Prompt families compared:

- **Baseline (historical, “same-day” bundle, 2026-01-26 PT)**:
  - 240: `simple-baseline` @ `git_sha=9276a569f43c19e22be92dcabcae0222b8485c15`
  - 600: `good-baseline` @ `git_sha=f41af8d21a5e3fda3827b0d2b890f121d9a98028`
  - 1200: `sota-xgb` @ `git_sha=3baf1d094169b1a9497d473fa3e34d3bd371a0bf`
  - Missing coverage was patched via `results/exp_promptfam_baseline_patch.sqlite`.
- **Time-gated (current)**:
  - 600: `good-baseline` + reasoning gate (experimental)
  - 1200: `sota-xgb` + reasoning gate (experimental)
- **Budget-aware (current)**:
  - 240/600/1200: `prompt_profile=budget-aware`

All artifacts:
- Design doc: `docs/experiments/prompt_families_v5_core.md`
- Auto-generated comparison: `docs/experiments/prompt_family_comparison_v5_core.md`
- Canonical merged per-run table: `results/exp_promptfam_comparison_runs.csv`

## Results (key takeaways)

### Important note on terminology (“baseline” vs prompt text)

“Baseline” here refers to the **policy choice** of which profile IDs we target at 240/600/1200.
However, the **exact prompt text** can differ across time because the prompt rendering strategy evolved:

- Legacy runs (including the historical baseline bundle above) used **Strategy 1**: `base_prompt.md` + `competition_overrides/<id>.md` (no `prompt_profiles/*` layer).
- Current runs use **Strategy 2**: `base_prompt.md` + `prompt_profiles/<profile>.md` + `competition_overrides/<id>.md`.

This is why “baseline” comparisons across different run batches must be treated carefully unless the runs are rerun under the same git SHA and prompt-rendering strategy.

### 1) Reliability (success rate) strongly favors baseline

Across the full v5_core grid:

- **Baseline:** 54/60 successes (~90%)
- **Budget-aware:** 38/60 successes
- **Time-gated:** 23/40 successes

Broken down by budget (successes / 20 runs per budget for the v5_core suite + 5 models):

| family | 240s | 600s | 1200s |
|---|---:|---:|---:|
| baseline | 18/20 | 17/20 | 19/20 |
| budget-aware | 12/20 | 14/20 | 12/20 |
| time-gated | — | 12/20 | 11/20 |

The reliability regressions are not evenly distributed: two of the five models were the main drivers.
In particular, `meta-llama/Meta-Llama-3.1-8B-Instruct` and `microsoft/Phi-3.5-mini-instruct` timed out frequently under the time-gated and budget-aware policies, while being much more reliable under baseline.

Model-level reliability signal (successes / 32 runs across all families/budgets/competitions in the experiment artifact):

| model | successes / 32 |
|---|---:|
| `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8` | 32/32 |
| `zai-org/GLM-4.6-FP8` | 30/32 |
| `deepseek-ai/DeepSeek-V3.1-Terminus` | 28/32 |
| `meta-llama/Meta-Llama-3.1-8B-Instruct` | 13/32 |
| `microsoft/Phi-3.5-mini-instruct` | 12/32 |

### 2) “More time helps” is not consistently monotonic under the new policies

Even when conditioning on successful runs only (ignoring timeouts), neither time-gated nor budget-aware produced a consistent “budget up ⇒ score up” pattern across competitions and models.

This is an expected failure mode in agentic ML:
- longer budgets increase the number of ways to fail (bugs, overfitting, selection mistakes),
- and can produce worse final outputs if the agent fails to preserve the best intermediate candidate.

### 3) Baseline exhibits the most intuitive budget scaling on strong models (but note confounding)

Baseline results looked more intuitive on the strong models (e.g. Qwen/GLM) on RMSE tasks.
However, baseline at 240/600/1200 is not a “pure” budget-scaling test because those budgets correspond to different profiles/commits.

## Decision

**Baseline is the project default prompt family going forward.**

Time-gated and budget-aware are retained as **experimental** prompt profiles (not default) to be used only when explicitly requested for experiments.

## Consequences

- Default runs should use the baseline profiles:
  - 240: `simple-baseline`
  - 600: `good-baseline`
  - 1200: `sota-xgb`
- Time-gated variants are stored separately and are **not** used unless explicitly overridden:
  - `good-baseline-timegated`
  - `sota-xgb-timegated`
- Budget-aware remains an experimental profile:
  - `budget-aware`
- Any future prompt-policy experiments must include reliability + monotonicity analysis as a standard report (see `docs/plan/selection_protocol.md`).

## Alternatives considered

- Make time-gated the default for “more thinking”: rejected due to large reliability regressions.
- Make budget-aware the default for all budgets: rejected due to regressions and non-monotonic behavior on some tasks.
