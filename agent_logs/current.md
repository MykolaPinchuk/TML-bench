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
- 2026-02-05 15:16:45 PST: Started full 3-model fill-in batch (2 reps, all 4 competitions, profiles 240/600/1200) using `orchestrator/model_sets/v5_5_user_selected3.json`, mode `v5_5_user_selected3_r2`, db `results/results_v5_5_user_selected3_r2.sqlite`, prompt strategy `profiled1`.
- 2026-02-05 19:58:40 PST: Added `a2a_notes.md` with mandatory async-run launch/monitor contract and linked it from onboarding entrypoints (`README.md`, `REPO_MAP.md`, `repo_workflow.md`, `onboarding.md`, `HANDOFF.md`). Implemented `scripts/async_suite_runner.py` (detached start/list/status/stop with run dir metadata + retries) and patched `orchestrator/sweep.py` parallel mode to import completed `result.json` records into sqlite as each run finishes, reducing progress loss on parent interruption.
- 2026-02-06 05:11:08 PST: Updated `results.md` with a new baseline-first (`profiled1`) section for latest runs: (a) `results/results_v5_5_user_selected3_r2_v2.sqlite` status (simple+sota complete; good-baseline missing 7 successful runs across 5 cells), and (b) completed Qwen top-up (`results/results_v5_5_qwen_topup3.sqlite`) with combined 5-run medians per competition/profile under Strategy 2.
- 2026-02-06 05:18:28 PST: Added Strategy-2 baseline-first `combined14` snapshot to `results.md` with 4 competition tables (14 models = old5 + working6 + new3), using best-success aggregation across profiled1 sources and explicit status cells where `good-baseline` gaps remain for `v5_5_user_selected3_r2_v2`.
