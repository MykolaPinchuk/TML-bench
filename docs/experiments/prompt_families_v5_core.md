# Prompt Families Experiment (v5_core)

This document locks the agreed experimental design for comparing prompt “families” on the Phase-5 runner.

Goal: avoid ambiguity about what was run and how to reproduce/extend it.

## Fixed scope

- **Suite:** `orchestrator/suites/v5_core.json` (4 competitions)
  - `bank-customer-churn-ict-u-ai`
  - `foot-traffic-wuerzburg-retail-forecasting-2-0`
  - `playground-series-s5e10`
  - `playground-series-s6e1`
- **Provider:** Chutes-only (**NanoGPT is retired**)
- **Models (5):** Chutes entries in `orchestrator/model_sets/v3_fast.json`
  - `deepseek-ai/DeepSeek-V3.1-Terminus`
  - `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`
  - `zai-org/GLM-4.6-FP8`
  - `meta-llama/Meta-Llama-3.1-8B-Instruct`
  - `microsoft/Phi-3.5-mini-instruct`
- **Budgets / specs:** 240 / 600 / 1200 seconds
- **Execution knobs:** `--runs-per-model 1`, `--concurrency 2`
- **DB hygiene:** do not reuse `results/results.sqlite` for new comparisons; write each family to its own DB file.

## Prompt families

We compare **three** families.

### A) Baseline (historical; “same-day” bundle, 2026-01-26 PT)

Baseline is defined as specific historical `git_sha` snapshots (per spec) from which runs already exist.

- 240s baseline: `simple-baseline` @ `git_sha=9276a569f43c19e22be92dcabcae0222b8485c15`
- 600s baseline: `good-baseline` @ `git_sha=f41af8d21a5e3fda3827b0d2b890f121d9a98028`
  - Missing cell: `playground-series-s6e1` @ 600 on Chutes → rerun just this cell to complete baseline coverage.
- 1200s baseline: `sota-xgb` @ `git_sha=3baf1d094169b1a9497d473fa3e34d3bd371a0bf`

Notes:
- “Same baseline prompt for all competitions” means the same prompt **templates/policy** at a pinned git commit; the rendered prompt still differs per competition because task text differs.
- Comparisons should filter by `provider='chutes'` to avoid historical NanoGPT results.

### B) Time-gated (current)

Run on current `v5` HEAD:
- 600s: `prompt_profile=good-baseline` (includes the remaining-time gate + “think hard” wording + 180s cap)
- 1200s: `prompt_profile=sota-xgb` (same gate)

No 240s run is required for this family (it does not modify `simple-baseline`).

### C) Budget-aware

Run on current `v5` HEAD:
- `prompt_profile=budget-aware` for **all three budgets**: 240/600/1200.

Existing budget-aware results in `results/results.sqlite` are incomplete/mixed; rerun the full grid for the agreed suite + 5 models.

## Recommended DB naming

Use separate DBs per family, e.g.:

- `results/exp_promptfam_timegated.sqlite`
- `results/exp_promptfam_budgetaware.sqlite`
- `results/exp_promptfam_baseline_patch.sqlite` (only the missing 600 cell rerun)

## Canonical commands (examples)

These are intentionally explicit; adjust only paths/DB names if needed.

Time-gated (current):
- `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile good-baseline --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_timegated.sqlite --only-provider chutes --mode pf_timegated`
- `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile sota-xgb --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_timegated.sqlite --only-provider chutes --mode pf_timegated`

Budget-aware (current):
- `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile simple-baseline --budget-seconds 240 --prompt-profile budget-aware --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_budgetaware.sqlite --only-provider chutes --mode pf_budgetaware`
- `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile good-baseline  --budget-seconds 600 --prompt-profile budget-aware --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_budgetaware.sqlite --only-provider chutes --mode pf_budgetaware`
- `python -m orchestrator.suite --models-path orchestrator/model_sets/v3_fast.json --profile sota-xgb       --budget-seconds 1200 --prompt-profile budget-aware --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_budgetaware.sqlite --only-provider chutes --mode pf_budgetaware`

Baseline missing-cell patch (requires baseline worktree at `f41af8d2...`):
- `python -m orchestrator.sweep --competition-id playground-series-s6e1 --models-path tmp/models_chutes_5.json --profile good-baseline --runs-per-model 1 --concurrency 2 --db-path results/exp_promptfam_baseline_patch.sqlite --only-provider chutes --mode pf_baseline_patch`

