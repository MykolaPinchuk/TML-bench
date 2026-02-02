# Prompt Family Comparison (v5_core)

Generated: `2026-02-01T16:40:59-08:00`

Scope: v5_core suite (4 competitions), 5 Chutes models, runs-per-model=1, concurrency=2.

Families / sources:
- Baseline: `results/results.sqlite` filtered to pinned `git_sha` per budget + patch from `results/exp_promptfam_baseline_patch.sqlite`.
- Time-gated: `results/exp_promptfam_timegated.sqlite`.
- Budget-aware: `results/exp_promptfam_budgetaware.sqlite`.

Aggregation notes:
- `mean`/`best` are computed over **successful** runs only (so timeouts don’t get an artificial score).
- `Δ vs baseline` is computed on the raw metric with `better > 0` (e.g. RMSE uses `baseline - other`, AUC uses `other - baseline`).

| competition | metric | budget | baseline succ/5 | baseline mean | time-gated succ/5 | time-gated mean | Δ vs base | budget-aware succ/5 | budget-aware mean | Δ vs base |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bank-customer-churn-ict-u-ai | auc | 240 | 4/5 | 0.924038 | — | — | — | 4/5 | 0.891089 | -0.032948 |
| bank-customer-churn-ict-u-ai | auc | 600 | 5/5 | 0.920659 | 3/5 | 0.925667 | 0.005008 | 5/5 | 0.911199 | -0.009461 |
| bank-customer-churn-ict-u-ai | auc | 1200 | 5/5 | 0.904024 | 3/5 | 0.925850 | 0.021826 | 3/5 | 0.922976 | 0.018952 |
| foot-traffic-wuerzburg-retail-forecasting-2-0 | rmse | 240 | 5/5 | 0.087615 | — | — | — | 3/5 | 0.068957 | 0.018658 |
| foot-traffic-wuerzburg-retail-forecasting-2-0 | rmse | 600 | 5/5 | 0.073063 | 3/5 | 0.068292 | 0.004771 | 3/5 | 0.068085 | 0.004978 |
| foot-traffic-wuerzburg-retail-forecasting-2-0 | rmse | 1200 | 5/5 | 0.066690 | 3/5 | 0.066000 | 0.000690 | 3/5 | 0.099037 | -0.032347 |
| playground-series-s5e10 | rmse | 240 | 4/5 | 0.056307 | — | — | — | 2/5 | 0.056659 | -0.000352 |
| playground-series-s5e10 | rmse | 600 | 5/5 | 0.056361 | 3/5 | 0.056216 | 0.000145 | 3/5 | 0.056306 | 0.000055 |
| playground-series-s5e10 | rmse | 1200 | 5/5 | 0.056386 | 3/5 | 0.056306 | 0.000080 | 3/5 | 0.056302 | 0.000084 |
| playground-series-s6e1 | rmse | 240 | 5/5 | 8.807601 | — | — | — | 3/5 | 9.023693 | -0.216092 |
| playground-series-s6e1 | rmse | 600 | 2/5 | 8.789488 | 3/5 | 8.993840 | -0.204351 | 3/5 | 8.916786 | -0.127297 |
| playground-series-s6e1 | rmse | 1200 | 4/5 | 8.750244 | 2/5 | 8.759922 | -0.009678 | 3/5 | 8.762565 | -0.012321 |

Artifacts:
- Per-run rows: `results/exp_promptfam_comparison_runs.csv`
- Aggregated summary: `results/exp_promptfam_comparison_summary.csv`
