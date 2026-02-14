# Paper Assets v1

This directory is a staging bundle of table/figure assets for the paper draft.

## Figures
- Source: `docs/paper/figures/v6/`
- Copied into: `figures/`
- Includes headline leaderboard, robustness variants, Result 0.5/2/3 plots.

## Tables
- `tables/canonical_5run_tables_from_results.md`
  - Extracted AUTO block from `results.md` (canonical 10-model 5-run median tables).
- `tables/canonical10_stability.md`
  - Copied from `docs/reports/v5_5_canonical10_stability.md`.
- `tables/*.csv`
  - Figure-derived tabular artifacts (leaderboard scores, consistency, reliability, scaling, token schema summaries).
- `tables/token_columns_union.txt`
  - Union of token/cost-like columns found in canonical sqlite sources.

Notes:
- This is intentionally a flat staging bundle for handoff.
- The next agent can restructure/curate these into final paper table/figure numbering.
