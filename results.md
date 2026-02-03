# Results (baseline)
This file is the **repo-root summary** of current benchmark results.

Decision: baseline prompt family is the project default. See `docs/adr/0003-default-prompt-family-baseline.md`.

## Prompting strategies (definitions)

We define prompt strategies by **single-word ids** under `prompts/strategies/`.

- **Strategy 1 = `legacy1`** (“base+override”, no profile layer)
  - Rendered prompt = `prompts/strategies/legacy1/base_prompt.md` + `prompts/strategies/legacy1/competition_overrides/<competition_id>.md`
- **Strategy 2 = `profiled1`** (“base+profile+override”)
  - Rendered prompt = `prompts/strategies/profiled1/base_prompt.md` + `prompts/strategies/profiled1/prompt_profiles/<profile>.md` + `prompts/strategies/profiled1/competition_overrides/<competition_id>.md`
  - `<profile>` is one of `simple-baseline` / `good-baseline` / `sota-xgb`.

Also:
- **`active`** = the live prompt files under `prompts/` (may evolve; do not use for “paper-grade” comparisons).

This file currently includes two snapshots:
- **v5.5 working models (recommended current view):** 6 new Chutes models that passed preflight and produced submissions across the full suite.
- **v5 legacy snapshot:** the older 5-model `v3_fast.json` table, kept for reference.

Prompting strategy note:
- The v5 legacy snapshot was generated under **Strategy 1**.
- The v5.5 working6 snapshot was generated under **Strategy 2**.

Note: these two snapshots are not guaranteed apples-to-apples unless the models are re-run under the same **prompt strategy id** and the same replication/selection policy.

Notes:
- Values are **private holdout** metrics (`score_raw`) when the run succeeded; otherwise the cell shows `timeout` / `invalid_submission` / etc.

## Snapshot: v5.5 working6 (Chutes-only; 6 models)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 6-model set from `orchestrator/model_sets/v5_5_chutes_working6.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)
- Prompt strategy: **Strategy 2 = `profiled1`**
- Source DB (not committed): `results/results_v5_5_working6_suite.sqlite`
- Selection rule: per cell, best successful `score_raw` over runs in `mode in {v5_5_working6, v5_5_working6_retry1}`

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.909941 | 0.924814 | 0.924826 | 0.925424 | 0.925413 | 0.826780 |
| 600 | 0.850738 | 0.919885 | 0.926785 | 0.927687 | 0.928364 | 0.926987 |
| 1200 | 0.922933 | 0.925431 | 0.920605 | 0.813105 | 0.916179 | 0.927429 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.106332 | 0.067424 | 0.070876 | 0.090144 | 0.068445 | 0.102616 |
| 600 | 0.070319 | 0.070643 | 0.067320 | 0.082290 | 0.066317 | 0.090884 |
| 1200 | 0.082189 | 0.066914 | 0.066512 | 0.080768 | 0.266041 | 0.080920 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.056991 | 0.059679 | 0.056384 | 0.059448 | 0.056362 | 0.056379 |
| 600 | 0.056311 | 0.056443 | 0.056274 | 0.056727 | 0.056383 | 0.056669 |
| 1200 | 0.056315 | 0.056226 | 0.056457 | 0.056367 | 0.056298 | 0.056254 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 8.878813 | 9.106100 | 8.878806 | 10.604385 | 8.897150 | 8.837352 |
| 600 | 13.564986 | 9.160990 | 9.123438 | 9.018375 | 9.729946 | 8.841146 |
| 1200 | 8.721937 | 8.758513 | 8.712406 | 8.740705 | 8.822877 | 8.768616 |

## Snapshot: v5 legacy (Chutes-only; `v3_fast.json` 5-model set)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 5-model set from `orchestrator/model_sets/v3_fast.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)
- Prompt strategy: **Strategy 1 = `legacy1`**

Notes:
- For the full prompt-family comparison (baseline vs budget-aware vs time-gated), see `docs/experiments/prompt_family_comparison_v5_core.md`.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | invalid_submission | 0.923990 | 0.922911 | 0.924543 | 0.924707 |
| 600 | 0.912099 | 0.922015 | 0.925680 | 0.921787 | 0.921714 |
| 1200 | 0.927889 | 0.927797 | 0.926654 | 0.927300 | 0.810482 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.082159 | 0.091228 | 0.082249 | 0.091225 | 0.091214 |
| 600 | 0.080706 | 0.080576 | 0.067860 | 0.068194 | 0.067980 |
| 1200 | 0.067152 | 0.066943 | 0.066531 | 0.066203 | 0.066622 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.056310 | 0.056302 | timeout | 0.056302 | 0.056313 |
| 600 | 0.056312 | 0.056291 | 0.056345 | 0.056416 | 0.056442 |
| 1200 | 0.056225 | 0.056231 | 0.057032 | 0.056195 | 0.056245 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 8.808302 | 8.806239 | 8.807874 | 8.808455 | 8.807136 |
| 600 | timeout | 8.780673 | 8.798304 | timeout | timeout |
| 1200 | 8.748496 | 8.746522 | 8.745623 | 8.760336 | timeout |

## Snapshot: v5.5 old5 profiled1 rep2 (Chutes-only; `v3_fast.json` 5-model set)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 5-model set from `orchestrator/model_sets/v3_fast.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)
- Prompt strategy: **Strategy 2 = `profiled1`**
- Source DB (not committed): `results/results_v5_5_v3fast_profiled1_r2.sqlite`
- Runs per cell: 2
- Selection rule: per cell, best successful `score_raw` over the 2 runs; if no success, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.928373 | 0.922710 | 0.927815 | timeout | timeout |
| 600 | 0.924451 | 0.928659 | 0.926028 | timeout | timeout |
| 1200 | 0.924792 | 0.928123 | 0.926563 | timeout | timeout |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.068472 | 0.066768 | 0.067363 | timeout | timeout |
| 600 | 0.166052 | 0.066198 | 0.066245 | timeout | timeout |
| 1200 | 0.065960 | 0.065874 | timeout | 0.081453 | timeout |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.056328 | 0.056353 | 0.056334 | timeout | timeout |
| 600 | 0.056272 | 0.056199 | 0.056224 | timeout | timeout |
| 1200 | 0.056199 | 0.056176 | 0.056175 | timeout | timeout |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 9.150546 | 9.117905 | 9.103240 | timeout | timeout |
| 600 | 8.792208 | 8.741439 | 8.779253 | 9.939816 | timeout |
| 1200 | 8.791701 | 8.728897 | 8.696671 | timeout | timeout |
