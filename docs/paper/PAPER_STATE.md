# PAPER_STATE

# This file is the only coordination surface between research and writer agents.
# Every agent should read it first.
#
# Conventions:
# - Research never edits an existing `paper_assets_vN/` in place; it creates `next_assets_dir`, then advances pointers.
# - Writer uses `active_assets_dir` as the evidence source for quantitative statements.

active_assets_dir: docs/paper/paper_assets_v3
next_assets_dir: docs/paper/paper_assets_v4
active_draft: docs/paper/draft_v1.md
active_claims: docs/paper/claims_matrix_v1.md
