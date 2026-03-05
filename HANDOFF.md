# HANDOFF

## Current slice
v6.5 reviewer-driven revision pass is in good shape. The draft now uses score-based leaderboard reporting in the main body, rank-based variants in appendix, expanded related work framing vs MLE-bench, contamination controls, refreshed model metadata, and appendix reorganization.

## Current state (2026-03-04)
- Branch state:
  - active branch: `v6.5`
  - latest checkpoint commit: `5a8aaa9` (`agent14: checkpoint(docs): update paper appendices and title date`)
- Paper artifacts (active):
  - markdown draft: `docs/paper/draft_v1.md`
  - claims matrix: `docs/paper/claims_matrix_v1.md`
  - LaTeX entrypoint: `docs/paper/tex_v1/main.tex`
  - LaTeX appendix sections: `docs/paper/tex_v1/sections/`
  - new competition appendix section: `docs/paper/tex_v1/sections/appendix_competitions.tex`
- Latest PDF build artifact:
  - `tmp/paper_build/main.pdf` (rebuilt on 2026-03-04; title page date is March 4, 2026)
- Paper workflow pointers:
  - contract: `docs/paper/PAPER_WORKFLOW.md`
  - state pointer: `docs/paper/PAPER_STATE.md`
  - writer prompts: `docs/paper/HUMAN_CHEATSHEET.md`
  - writer playbook: `docs/paper/WRITER_PLAYBOOK.md`
- Active evidence bundle for writing:
  - `docs/paper/paper_assets_v3/` (`next_assets_dir`: `docs/paper/paper_assets_v4`)

## What changed in this cycle
- Replaced informal phrasing and normalized terminology around primary model-comparison results.
- Added and clarified the score normalization method in both LaTeX and markdown drafts.
- Kept rank-based views as supplementary appendix material (heatmap retained in main body).
- Expanded related-work comparison and explicit TML-bench advantages over MLE-bench.
- Added contamination-controls language (internet-off runs + pretraining-cutoff-before-competition framing).
- Refactored appendix organization to group small figure-only items into coherent appendix subsections.
- Updated Appendix A model inventory:
  - renamed headers (`Model`, `Parameters`, `Release date`)
  - added/updated knowledge cutoff dates (including Nemotron cutoff at 2025-06-25)
  - improved table layout to avoid text overlap and forced placement under Appendix A heading.
- Added new appendix with four-competition details:
  - problem type/target, metric, train/test rows, feature counts.
- Updated title-page date and verified rendered PDF output text.

## Immediate next plan (for next agent)
1. Run one final editorial consistency pass across LaTeX + markdown + claims matrix.
2. Check that every figure/table reference in text is explicit and correctly placed.
3. Validate Appendix A sourcing language for any cutoff entries that are inferred/unofficial.
4. Build final PDF and do a quick visual pass for table/figure layout warnings.
5. Prepare first-draft freeze checkpoint if user confirms no further content edits.

## Deferred items (unchanged unless explicitly requested)
- Token/cost efficiency analysis (blocked by missing token telemetry in canonical DB schema; only `max_tokens` available).
- Promotion from canonical 10-model reporting to 14-model reporting (requires full 5-run coverage across all 12 cells).
- Broader v7 expansions (non-agentic baselines, deeper literature sweep).

## Key evidence paths
- Canonical results snapshot: `results.md`
- Canonical stability companion: `docs/reports/v5_5_canonical10_stability.md`
- Results refresh/check scripts:
  - `scripts/refresh_profiled1_results.py`
  - `scripts/check_profiled1_canonical_coverage.py`
- Paper sources:
  - `docs/paper/draft_v1.md`
  - `docs/paper/claims_matrix_v1.md`
  - `docs/paper/tex_v1/main.tex`
  - `docs/paper/tex_v1/sections/appendix_competitions.tex`
- Paper workflow/state:
  - `docs/paper/PAPER_WORKFLOW.md`
  - `docs/paper/PAPER_STATE.md`
  - `docs/paper/HUMAN_CHEATSHEET.md`
  - `docs/paper/WRITER_PLAYBOOK.md`

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep `profiled1` canonical reporting policy intact unless user explicitly changes it.
- Keep suite safety behavior intact (`orchestrator/suite.py`, including foot-traffic concurrency cap).
