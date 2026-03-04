# Reproducibility Appendix v1

This appendix defines the canonical regeneration and verification flow for the v6 draft-first slice.

## Preconditions

- Run from repo root.
- Python environment with project dependencies available.
- Existing canonical sqlite inputs present under `results/`.

## Commands

```bash
python scripts/refresh_profiled1_results.py
python scripts/check_profiled1_canonical_coverage.py
```

## Plot generation (leaderboard variants)

The v6 draft uses within-setting min-max normalized scores computed from canonical 5-run medians.

Generate all three leaderboard variants (primary + robustness checks):

```bash
python scripts/render_v6_leaderboard_plots.py --out-dir docs/paper/figures/v6
```

Draft figures are committed under: `docs/paper/figures/v6/`

Expected files:
- `docs/paper/figures/v6/leaderboard_best_budget_per_comp.png` (primary: best budget per competition)
- `docs/paper/figures/v6/leaderboard_overall_all_cells.png` (robustness: overall across all competitions and budgets)
- `docs/paper/figures/v6/leaderboard_sota_only.png` (robustness: sota-only)
- `docs/paper/figures/v6/leaderboard_scores.csv` (raw aggregate scores for all variants)

## Plot generation (Result 0.5/2/3)

Generate the additional v6 key-result figures (consistency, reliability, scaling):

```bash
python scripts/render_v6_key_results_plots.py --out-dir docs/paper/figures/v6
```

Expected files (selection):
- `docs/paper/figures/v6/result0_5_consistency_ranks_heatmap.png`
- `docs/paper/figures/v6/result2_pareto_performance_vs_stability.png`
- `docs/paper/figures/v6/result3_scaling_points_lines.png`

## Expected verification contract

Coverage checker output must include:

- `sources_found=9/9`
- `canonical_models=10`
- `missing_cells=0`
- `results_md_declared_coverage=10`
- `results_md_declared_models=10`
- `status=OK`

If any condition fails, treat the canonical tables as not frozen and do not publish updated draft claims until resolved.

## Primary evidence paths used by draft v1

- Canonical medians and run-status snapshot: `results.md`
- Stability/IQR companion: `docs/reports/v5_5_canonical10_stability.md`
- Active slice plan and constraints: `docs/plan/v6.md`
- Current handoff state: `HANDOFF.md`

## Notes on deferred scope

The 4-model backfill track remains non-canonical in this draft slice. Do not fold partial 14-model coverage into primary leaderboard claims.

## Notes on token accounting

Current canonical sqlite sources do not include token usage or cost fields. A schema summary is emitted by the key-results plot generator:
- `docs/paper/figures/v6/token_columns_union.txt`
- `docs/paper/figures/v6/token_columns_by_db.csv`
