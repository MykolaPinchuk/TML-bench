# Results (baseline)

This file is the **repo-root summary** of current benchmark results.

Decision: baseline prompt family is the project default. See `docs/adr/0003-default-prompt-family-baseline.md`.

Scope of the snapshot below:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 5-model set from `orchestrator/model_sets/v3_fast.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)

Notes:
- Values are **private holdout** metrics (`score_raw`) when the run succeeded; otherwise the cell shows `timeout` / `invalid_submission`.
- For the full prompt-family comparison (baseline vs budget-aware vs time-gated), see `docs/experiments/prompt_family_comparison_v5_core.md`.

## bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | invalid_submission | 0.923990 | 0.922911 | 0.924543 | 0.924707 |
| 600 | 0.912099 | 0.922015 | 0.925680 | 0.921787 | 0.921714 |
| 1200 | 0.927889 | 0.927797 | 0.926654 | 0.927300 | 0.810482 |

## foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.082159 | 0.091228 | 0.082249 | 0.091225 | 0.091214 |
| 600 | 0.080706 | 0.080576 | 0.067860 | 0.068194 | 0.067980 |
| 1200 | 0.067152 | 0.066943 | 0.066531 | 0.066203 | 0.066622 |

## playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.056310 | 0.056302 | timeout | 0.056302 | 0.056313 |
| 600 | 0.056312 | 0.056291 | 0.056345 | 0.056416 | 0.056442 |
| 1200 | 0.056225 | 0.056231 | 0.057032 | 0.056195 | 0.056245 |

## playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 8.808302 | 8.806239 | 8.807874 | 8.808455 | 8.807136 |
| 600 | timeout | 8.780673 | 8.798304 | timeout | timeout |
| 1200 | 8.748496 | 8.746522 | 8.745623 | 8.760336 | timeout |

