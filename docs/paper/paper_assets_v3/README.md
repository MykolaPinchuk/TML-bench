# Paper Assets v3

This directory is a frozen staging bundle of table/figure assets for writer drafting.

Generated: 2026-03-03 18:59:45 PST

## Figures
- Source: `docs/paper/figures/v6/`
- Copied into: `figures/`
- Inventory: `11` plots (PNG), `10` figure CSV companions, `1` figure TXT companion.

## Tables
- `tables/canonical_5run_tables_from_results.md`
  - Extracted AUTO block from `results.md` (canonical 10-model 5-run median tables).
- `tables/canonical10_stability.md`
  - Copied from `docs/reports/v5_5_canonical10_stability.md`.
- `tables/*.csv` and `tables/token_columns_union.txt`
  - Figure-derived tabular artifacts for leaderboard, consistency, reliability, scaling, and token-schema diagnostics.
- Inventory: `13` table artifacts.

Notes:
- This bundle is read-only evidence input for the writer.
- Leaderboard normalization in this bundle uses within-setting min-max normalization (absolute metric gaps), not rank-based points.
- Use `docs/paper/PAPER_STATE.md` to discover the currently active bundle.
