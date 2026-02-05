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

Current run policy:
- **Default baseline strategy:** use **Strategy 2 = `profiled1`** for primary benchmark reporting.
- **Robustness strategy:** run **Strategy 1 = `legacy1`** only when explicitly requested as a robustness/sensitivity check.

This file currently includes four snapshots:
- **v5.5 combined view (11 models):** old5 + working6, each shown under Strategy 1 and Strategy 2 (single tables for easy scanning).
- **v5.5 working models (recommended current view):** 6 new Chutes models, reported under both Strategy 2 (`profiled1`) and Strategy 1 (`legacy1`) with 2-run replication.
- **v5 legacy snapshot:** the older 5-model `v3_fast.json` table, kept for reference.
- **v5.5 old5 under Strategy 2:** the same older 5-model `v3_fast.json` set, re-run under `profiled1` for strategy comparison.

Note: snapshots are not guaranteed apples-to-apples unless the models are re-run under the same **prompt strategy id** and the same replication/selection policy.

Notes:
- Values are **private holdout** metrics (`score_raw`) when the run succeeded; otherwise the cell shows `timeout` / `invalid_submission` / etc.
- Each snapshot explicitly defines its replication/selection policy (e.g., “best of 2 successful runs”).

## Apples-to-apples strategy comparison (what to use)

If you want a clean **Strategy 1 (`legacy1`) vs Strategy 2 (`profiled1`)** comparison with:
- success rates,
- monotonicity across budgets (240→600→1200),
- strong models outperforming weak models,

use only **controlled run batches** where both strategies have comparable replication.

Current controlled batches:
- **working6 (new6)**
  - `legacy1` (2 runs/cell): `results/results_v5_5_working6_legacy1_r2_probe_churn.sqlite` + `results/results_v5_5_working6_legacy1_r1_remaining3.sqlite`
  - `profiled1` (2 reps/cell): rep1 `results/results_v5_5_working6_suite.sqlite` + rep2 `results/results_v5_5_working6_profiled1_rep2.sqlite`
- **old5 (`v3_fast.json`)**
  - `profiled1` (2 runs/cell): `results/results_v5_5_v3fast_profiled1_r2.sqlite`
  - `legacy1` (2 runs/cell): `results/results_v5_5_v3fast_legacy1_r2.sqlite` (mode `v5_5_v3fast_legacy1_r2`)

Strategy comparison summary (current; best-of-2 selection policy, 2026-02-05):
- **old5 (60 cells = 4 comps × 3 budgets × 5 models)**:
  - Success rate: `legacy1` 34/60 (56.7%) vs `profiled1` 37/60 (61.7%)
  - Among 33 cells where both strategies succeeded: `profiled1` wins 23 vs `legacy1` wins 10
- **working6 (72 cells = 4 comps × 3 budgets × 6 models)**:
  - Success rate: `legacy1` 62/72 (86.1%) vs `profiled1` 72/72 (100.0%)
  - Among 62 cells where both strategies succeeded: wins are tied (31 vs 31)

Important: under `profiled1`, the 240/600/1200 budgets also change the **profile text layer** (`simple-baseline`/`good-baseline`/`sota-xgb`), so “monotonic with budget” reflects “more time + different profile”, not just “more time”.

## Snapshot: v5.5 combined11 (Chutes-only; 11 models)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: old5 (`orchestrator/model_sets/v3_fast.json`) + working6 (`orchestrator/model_sets/v5_5_chutes_working6.json`)
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)

### Strategy 1: `legacy1` (2 runs; best-of-2)

Sources (not committed):
- old5: `results/results_v5_5_v3fast_legacy1_r2.sqlite` (mode `v5_5_v3fast_legacy1_r2`)
- working6 churn: `results/results_v5_5_working6_legacy1_r2_probe_churn.sqlite`
- working6 remaining3: `results/results_v5_5_working6_legacy1_r1_remaining3.sqlite`
- Selection rule: per cell, best successful `score_raw` over the 2 runs; if no success, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.923150 | 0.922726 | 0.922244 | timeout | timeout | 0.920076 | 0.925617 | 0.918941 | timeout | 0.928191 | 0.926983 |
| 600 | 0.924277 | 0.924515 | 0.924082 | timeout | timeout | 0.920300 | 0.928061 | 0.924196 | timeout | 0.927576 | 0.926733 |
| 1200 | timeout | 0.926168 | 0.926976 | timeout | timeout | 0.916006 | 0.928219 | 0.925864 | 0.924545 | 0.925016 | 0.928108 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.069570 | 0.065313 | 0.066096 | timeout | timeout | timeout | 0.070234 | 0.066252 | 0.078540 | 0.065724 | 0.076923 |
| 600 | 0.066615 | 0.065637 | 0.066919 | timeout | timeout | timeout | 0.069031 | 0.066033 | 0.193444 | 0.066375 | 0.084981 |
| 1200 | 0.067510 | 0.065897 | 0.065686 | timeout | timeout | 0.079781 | 0.066291 | 0.071177 | 0.109078 | 0.065199 | 0.076900 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | timeout | 0.056819 | 0.056308 | timeout | timeout | 0.059462 | 0.056296 | 0.056312 | 0.059393 | 0.056295 | 0.057954 |
| 600 | 0.056350 | 0.056736 | 0.056235 | timeout | timeout | 0.059510 | 0.056318 | 0.056990 | 0.058756 | 0.056234 | 0.057928 |
| 1200 | 0.056209 | 0.056212 | 0.056208 | timeout | timeout | runtime_error | 0.056215 | 0.056209 | 0.056367 | 0.056196 | 0.058028 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 9.158417 | 9.085194 | 8.906414 | timeout | timeout | runtime_error | 9.169291 | 9.060212 | timeout | 8.807914 | 8.893176 |
| 600 | 9.163334 | 8.802716 | 8.838196 | timeout | timeout | 9.057829 | 8.952142 | 8.767334 | 8.767829 | 8.792463 | 8.842876 |
| 1200 | 8.789005 | 8.747630 | 8.731338 | timeout | timeout | 8.799415 | timeout | timeout | timeout | 8.744021 | 8.842876 |

### Strategy 2: `profiled1` (2 reps; best-of-2)

Sources (not committed):
- old5: `results/results_v5_5_v3fast_profiled1_r2.sqlite` (2 runs/cell)
- working6 rep1: `results/results_v5_5_working6_suite.sqlite` (modes `v5_5_working6` + `v5_5_working6_retry1`)
- working6 rep2: `results/results_v5_5_working6_profiled1_rep2.sqlite` (mode prefix `v5_5_working6_profiled1_rep2%`)
- Selection rule: per cell, take the best successful `score_raw` from each rep (if any), then pick the best of the 2 reps; if neither rep succeeded, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.928373 | 0.922710 | 0.927815 | timeout | timeout | 0.909941 | 0.924814 | 0.924826 | 0.925424 | 0.925413 | 0.925956 |
| 600 | 0.924451 | 0.928659 | 0.926028 | timeout | timeout | 0.850738 | 0.919885 | 0.927855 | 0.927687 | 0.928364 | 0.926987 |
| 1200 | 0.924792 | 0.928123 | 0.926563 | timeout | timeout | 0.922933 | 0.925522 | 0.922392 | 0.917111 | 0.922475 | 0.928149 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.068472 | 0.066768 | 0.067363 | timeout | timeout | 0.083345 | 0.067424 | 0.070876 | 0.090144 | 0.068445 | 0.091271 |
| 600 | 0.166052 | 0.066198 | 0.066245 | timeout | timeout | 0.070319 | 0.070643 | 0.067320 | 0.082290 | 0.066317 | 0.090884 |
| 1200 | 0.065960 | 0.065874 | timeout | 0.081453 | timeout | 0.082189 | 0.066719 | 0.065670 | 0.078471 | 0.065235 | 0.080876 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.056328 | 0.056353 | 0.056334 | timeout | timeout | 0.056991 | 0.059679 | 0.056384 | 0.056971 | 0.056293 | 0.056324 |
| 600 | 0.056272 | 0.056199 | 0.056224 | timeout | timeout | 0.056311 | 0.056443 | 0.056274 | 0.056727 | 0.056383 | 0.056669 |
| 1200 | 0.056199 | 0.056176 | 0.056175 | timeout | timeout | 0.056229 | 0.056181 | 0.056232 | 0.056158 | 0.056298 | 0.056254 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B | NVIDIA-Nemotron-3-Nano | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 9.150546 | 9.117905 | 9.103240 | timeout | timeout | 8.878813 | 9.106100 | 8.878806 | 10.604385 | 8.770655 | 8.837352 |
| 600 | 8.792208 | 8.741439 | 8.779253 | 9.939816 | timeout | 13.444163 | 8.808211 | 8.780335 | 9.018375 | 8.767801 | 8.738090 |
| 1200 | 8.791701 | 8.728897 | 8.696671 | timeout | timeout | 8.721937 | 8.758513 | 8.712406 | 8.740705 | 8.822877 | 8.760239 |

## Snapshot: v5.5 working6 (Chutes-only; 6 models)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 6-model set from `orchestrator/model_sets/v5_5_chutes_working6.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)

### Strategy 2: `profiled1` (2 reps; best-of-2)

Scope:
- Prompt strategy: **Strategy 2 = `profiled1`**
- Rep 1 source DB (not committed): `results/results_v5_5_working6_suite.sqlite` (runs in `mode in {v5_5_working6, v5_5_working6_retry1}`)
- Rep 2 source DB (not committed): `results/results_v5_5_working6_profiled1_rep2.sqlite` (runs in `mode like v5_5_working6_profiled1_rep2%`)
- Runs per cell: 2 reps
- Selection rule: per cell, take the best successful `score_raw` from each rep (if any), then pick the best of the 2 reps; if neither rep succeeded, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.909941 | 0.924814 | 0.924826 | 0.925424 | 0.925413 | 0.925956 |
| 600 | 0.850738 | 0.919885 | 0.927855 | 0.927687 | 0.928364 | 0.926987 |
| 1200 | 0.922933 | 0.925522 | 0.922392 | 0.917111 | 0.922475 | 0.928149 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.083345 | 0.067424 | 0.070876 | 0.090144 | 0.068445 | 0.091271 |
| 600 | 0.070319 | 0.070643 | 0.067320 | 0.082290 | 0.066317 | 0.090884 |
| 1200 | 0.082189 | 0.066719 | 0.065670 | 0.078471 | 0.065235 | 0.080876 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.056991 | 0.059679 | 0.056384 | 0.056971 | 0.056293 | 0.056324 |
| 600 | 0.056311 | 0.056443 | 0.056274 | 0.056727 | 0.056383 | 0.056669 |
| 1200 | 0.056229 | 0.056181 | 0.056232 | 0.056158 | 0.056298 | 0.056254 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 8.878813 | 9.106100 | 8.878806 | 10.604385 | 8.770655 | 8.837352 |
| 600 | 13.444163 | 8.808211 | 8.780335 | 9.018375 | 8.767801 | 8.738090 |
| 1200 | 8.721937 | 8.758513 | 8.712406 | 8.740705 | 8.822877 | 8.760239 |

### Strategy 1: `legacy1` (2 runs; best-of-2)

Scope:
- Prompt strategy: **Strategy 1 = `legacy1`**
- Source DBs (not committed):
  - `bank-customer-churn-ict-u-ai`: `results/results_v5_5_working6_legacy1_r2_probe_churn.sqlite`
  - Remaining 3 competitions: `results/results_v5_5_working6_legacy1_r1_remaining3.sqlite`
- Runs per cell: 2
- Selection rule: per cell, best successful `score_raw` over the 2 runs; if no success, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.920076 | 0.925617 | 0.918941 | timeout | 0.928191 | 0.926983 |
| 600 | 0.920300 | 0.928061 | 0.924196 | timeout | 0.927576 | 0.926733 |
| 1200 | 0.916006 | 0.928219 | 0.925864 | 0.924545 | 0.925016 | 0.928108 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | timeout | 0.070234 | 0.066252 | 0.078540 | 0.065724 | 0.076923 |
| 600 | timeout | 0.069031 | 0.066033 | 0.193444 | 0.066375 | 0.084981 |
| 1200 | 0.079781 | 0.066291 | 0.071177 | 0.109078 | 0.065199 | 0.076900 |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | 0.059462 | 0.056296 | 0.056312 | 0.059393 | 0.056295 | 0.057954 |
| 600 | 0.059510 | 0.056318 | 0.056990 | 0.058756 | 0.056234 | 0.057928 |
| 1200 | runtime_error | 0.056215 | 0.056209 | 0.056367 | 0.056196 | 0.058028 |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek TNG R1T2 Chimera | Kimi K2 Instruct 0905 | Devstral-2-123B-Instruct-2512-TEE | NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | GLM 4.7 Flash | GPT OSS 120B TEE |
|---:|---:|---:|---:|---:|---:|---:|
| 240 | runtime_error | 9.169291 | 9.060212 | timeout | 8.807914 | 8.893176 |
| 600 | 9.057829 | 8.952142 | 8.767334 | 8.767829 | 8.792463 | 8.842876 |
| 1200 | 8.799415 | timeout | timeout | timeout | 8.744021 | 8.842876 |

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

## Snapshot: v5.5 old5 legacy1 rep2 (Chutes-only; `v3_fast.json` 5-model set)

Scope:
- Suite: v5_core (4 competitions)
- Provider: Chutes-only
- Models: 5-model set from `orchestrator/model_sets/v3_fast.json`
- Budgets: 240 / 600 / 1200 seconds
- Prompt family: **baseline** (240=`simple-baseline`, 600=`good-baseline`, 1200=`sota-xgb`)
- Prompt strategy: **Strategy 1 = `legacy1`**
- Source DB (not committed): `results/results_v5_5_v3fast_legacy1_r2.sqlite`
- Mode: `v5_5_v3fast_legacy1_r2`
- Runs per cell: 2
- Selection rule: per cell, best successful `score_raw` over the 2 runs; if no success, show the most common failure status.

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.923150 | 0.922726 | 0.922244 | timeout | timeout |
| 600 | 0.924277 | 0.924515 | 0.924082 | timeout | timeout |
| 1200 | timeout | 0.926168 | 0.926976 | timeout | timeout |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 0.069570 | 0.065313 | 0.066096 | timeout | timeout |
| 600 | 0.066615 | 0.065637 | 0.066919 | timeout | timeout |
| 1200 | 0.067510 | 0.065897 | 0.065686 | timeout | timeout |

### playground-series-s5e10 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | timeout | 0.056819 | 0.056308 | timeout | timeout |
| 600 | 0.056350 | 0.056736 | 0.056235 | timeout | timeout |
| 1200 | 0.056209 | 0.056212 | 0.056208 | timeout | timeout |

### playground-series-s6e1 (RMSE; lower is better)

| budget | DeepSeek-V3.1-Terminus | Qwen3-Coder-480B-A35B | GLM-4.6 | Llama-3.1-8B | Phi-3.5-mini |
|---:|---:|---:|---:|---:|---:|
| 240 | 9.158417 | 9.085194 | 8.906414 | timeout | timeout |
| 600 | 9.163334 | 8.802716 | 8.838196 | timeout | timeout |
| 1200 | 8.789005 | 8.747630 | 8.731338 | timeout | timeout |

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
