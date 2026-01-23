# Repo-specific agent notes (TML-bench)

## Phase and branching model
- Branches are phase-aligned: `v0` (setup), then `v1`, `v2`, ... matching PRD phases.
- Only the human pushes; agents may create local commits when asked (`checkpoint` / `handoff`).

## Data and artifacts hygiene (non-negotiable)
- Never commit Kaggle data, generated competition data, private labels, submissions, transcripts, workspaces, sqlite DBs, or other bulky artifacts.
- Treat anything under `competitions/**/{public,private,raw,downloads}/` and `runs/` as untracked outputs.

## Benchmark security posture
- Phases 1–5 are “functionality only, not secure”.
- Phase 6 introduces hard enforcement (isolation + egress allowlist + strict mounts).

## Time limits
- Default to short commands with timeouts; avoid long-running jobs unless explicitly requested.
