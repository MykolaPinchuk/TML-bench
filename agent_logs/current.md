# agent_logs/current.md

## Agent
- id: agent08

## Timestamp (Pacific)
- start: 2026-02-05

## Intent
- v5.5 continuation: keep `profiled1` as default baseline, expand model set, and produce less noisy reporting with 5-run medians.

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).
- Treat `legacy1` as robustness-only unless explicitly requested.

## Log
- 2026-02-05 14:04:59 PST: Onboarded current v5.5 context. Confirmed default run policy is --prompt-strategy profiled1 with baseline profiles, legacy1 is robustness-only, and current suite remains 4 competitions (v5_core). Immediate next-step focus: prepare a 5-competition suite file + expanded tool-capable model set, then run replicated sweeps (runs-per-model=5) with median-first reporting and success-rate sidecar.
- 2026-02-05 14:26:01 PST: Added `orchestrator/model_sets/v5_5_user_probe5.json` (GLM-4.7-TEE, GLM-4.7-FP8, MiMo-V2-Flash, MiniMax-M2.1-TEE, grok-4.1-fast). Preflight (60s/model) passed 4/5 (MiMo timeout). Ran smoke sweep on `bank-customer-churn-ict-u-ai` with `--profile simple-baseline --prompt-strategy profiled1 --runs-per-model 1 --concurrency 5` into `results/results_v5_5_user_probe5_smoke.sqlite`; all 5 runs succeeded. AUCs: MiniMax 0.926932, grok 0.926208, GLM-4.7-FP8 0.920895, GLM-4.7-TEE 0.918691, MiMo 0.770342.
- 2026-02-05 14:39:16 PST: Ran 600s smoke (no MiMo) on `bank-customer-churn-ict-u-ai` using `tmp/preflight/v5_5_user_probe5.filtered.json` with `--profile good-baseline --prompt-strategy profiled1 --runs-per-model 1 --concurrency 4` into `results/results_v5_5_user_probe4_smoke_600.sqlite`; all 4 runs succeeded. AUCs: GLM-4.7-TEE 0.926392, MiniMax-M2.1-TEE 0.924867, grok-4.1-fast 0.922859, GLM-4.7-FP8 0.921976.
- 2026-02-05 15:11:05 PST: Ran GLM-4.7 head-to-head duel on `bank-customer-churn-ict-u-ai` with `--prompt-strategy profiled1` in `results/results_v5_5_glm47_duel.sqlite` (3 reps/model at 240s + 3 reps/model at 600s). 240s medians: TEE 0.922031 vs FP8 0.923465; 600s medians: TEE 0.927232 vs FP8 0.927369; all 12 runs succeeded. Selected `zai-org/GLM-4.7-FP8` over `zai-org/GLM-4.7-TEE` and wrote final set `orchestrator/model_sets/v5_5_user_selected3.json` with FP8 + MiniMax + grok.
