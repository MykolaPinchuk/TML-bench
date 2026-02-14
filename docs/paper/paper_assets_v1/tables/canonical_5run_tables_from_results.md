<!-- AUTO:PROFILED1_FIVERUN_START -->

### 0.1) Dedicated 5-run median tables (auto-updated; complete models only)

Method:
- For each `(competition, model, profile)` cell, take the earliest 5 successful `profiled1` runs by `created_at` and compute median `score_raw`.
- Include only models with full `12/12` cells at 5 runs.

Coverage snapshot: **10 models** currently satisfy the 5-run criterion.

Source DBs used:
- `results/results_v5_5_v3fast_profiled1_r2.sqlite`
- `results/results_v5_5_working6_suite.sqlite`
- `results/results_v5_5_working6_profiled1_rep2.sqlite`
- `results/results_v5_5_user_selected3_r2_v2.sqlite`
- `results/results_v5_5_qwen_topup3.sqlite`
- `results/results_v5_5_topup3models_r5.sqlite`
- `results/results_v5_5_topup6_waveA_r5_seeded.sqlite`
- `results/results_v5_5_topup3_waveB_r5_seeded.sqlite`
- `results/results_v5_5_topup_remaining5_r5_seeded.sqlite`

Complete models in scope:
- `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`
- `openai/gpt-oss-120b-TEE`
- `zai-org/GLM-4.7-FP8`
- `zai-org/GLM-4.7-Flash`
- `MiniMaxAI/MiniMax-M2.1-TEE`
- `zai-org/GLM-4.6-FP8`
- `deepseek-ai/DeepSeek-V3.1-Terminus`
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`
- `mistralai/Devstral-2-123B-Instruct-2512-TEE`
- `tngtech/DeepSeek-TNG-R1T2-Chimera`

### bank-customer-churn-ict-u-ai (AUC; higher is better)

| profile | Qwen3-Coder-480B-A35B | GPT OSS 120B TEE | GLM-4.7-FP8 | GLM 4.7 Flash | MiniMax-M2.1-TEE | GLM-4.6-FP8 | DeepSeek-V3.1-Terminus | NVIDIA-Nemotron-3-Nano | mistralai/Devstral-2-123B-Instruct-2512-TEE | tngtech/DeepSeek-TNG-R1T2-Chimera |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| simple-baseline (240s) | 0.918860 | 0.886890 | 0.923560 | 0.924952 | 0.926671 | 0.925905 | 0.923724 | 0.921932 | 0.924826 | 0.868734 |
| good-baseline (600s) | 0.927958 | 0.926987 | 0.926432 | 0.926830 | 0.925957 | 0.921539 | 0.924738 | 0.887052 | 0.926987 | 0.884988 |
| sota-xgb (1200s) | 0.926755 | 0.928000 | 0.924275 | 0.922475 | 0.926496 | 0.920729 | 0.924792 | 0.813105 | 0.924461 | 0.921846 |

### foot-traffic-wuerzburg-retail-forecasting-2-0 (RMSE; lower is better)

| profile | Qwen3-Coder-480B-A35B | GPT OSS 120B TEE | GLM-4.7-FP8 | GLM 4.7 Flash | MiniMax-M2.1-TEE | GLM-4.6-FP8 | DeepSeek-V3.1-Terminus | NVIDIA-Nemotron-3-Nano | mistralai/Devstral-2-123B-Instruct-2512-TEE | tngtech/DeepSeek-TNG-R1T2-Chimera |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| simple-baseline (240s) | 0.070603 | 0.091293 | 0.067629 | 0.070913 | 0.066846 | 0.067414 | 0.068217 | 0.090144 | 0.070351 | 0.102553 |
| good-baseline (600s) | 0.066528 | 0.090884 | 0.066475 | 0.066729 | 0.065770 | 0.066564 | 0.068627 | 0.082290 | 0.067983 | 0.091104 |
| sota-xgb (1200s) | 0.066263 | 0.080920 | 0.066571 | 0.107502 | 0.065489 | 0.067095 | 0.065664 | 0.080768 | 0.067383 | 0.082189 |

### playground-series-s5e10 (RMSE; lower is better)

| profile | Qwen3-Coder-480B-A35B | GPT OSS 120B TEE | GLM-4.7-FP8 | GLM 4.7 Flash | MiniMax-M2.1-TEE | GLM-4.6-FP8 | DeepSeek-V3.1-Terminus | NVIDIA-Nemotron-3-Nano | mistralai/Devstral-2-123B-Instruct-2512-TEE | tngtech/DeepSeek-TNG-R1T2-Chimera |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| simple-baseline (240s) | 0.059786 | 0.056965 | 0.056363 | 0.056293 | 0.056200 | 0.056334 | 0.056328 | 0.059448 | 0.056606 | 0.073754 |
| good-baseline (600s) | 0.056924 | 0.056943 | 0.056258 | 0.056383 | 0.056202 | 0.057684 | 0.056299 | 0.056928 | 0.056274 | 0.056918 |
| sota-xgb (1200s) | 0.056212 | 0.056288 | 0.056212 | 0.056457 | 0.056195 | 0.056190 | 0.056199 | 0.056367 | 0.056232 | 0.056315 |

### playground-series-s6e1 (RMSE; lower is better)

| profile | Qwen3-Coder-480B-A35B | GPT OSS 120B TEE | GLM-4.7-FP8 | GLM 4.7 Flash | MiniMax-M2.1-TEE | GLM-4.6-FP8 | DeepSeek-V3.1-Terminus | NVIDIA-Nemotron-3-Nano | mistralai/Devstral-2-123B-Instruct-2512-TEE | tngtech/DeepSeek-TNG-R1T2-Chimera |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| simple-baseline (240s) | 9.145977 | 8.844860 | 8.788779 | 8.897150 | 8.754980 | 9.097556 | 9.157792 | 9.054929 | 9.107469 | 8.879082 |
| good-baseline (600s) | 8.805455 | 8.839272 | 8.757437 | 8.777121 | 8.757597 | 8.843763 | 9.103686 | 9.037052 | 9.111322 | 10.199380 |
| sota-xgb (1200s) | 8.728897 | 8.760239 | 8.730949 | 8.756742 | 8.699779 | 8.705116 | 8.711680 | 8.740705 | 8.715448 | 8.736438 |

<!-- AUTO:PROFILED1_FIVERUN_END -->
