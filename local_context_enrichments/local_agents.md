# Repo-specific agent notes (TML-bench)

## Phase and branching model
- Branches are phase-aligned: `v0` (setup), then `v1`, `v2`, ... matching PRD phases.
- Only the human pushes; agents may create local commits when asked (`checkpoint` / `handoff`).
- Agents may also create **additional** safe checkpoint commits proactively after coherent milestones.
- Never start work on `vN+1` (next phase) without explicit human approval.

## Commit message format
- All commits must include agent number (derive from `agent_logs/current.md` `id:`):
  - `agentNN: checkpoint(<area>): <summary>`
  - `agentNN: handoff(<area>): <summary>`

## Data and artifacts hygiene (non-negotiable)
- Never commit Kaggle data, generated competition data, private labels, submissions, transcripts, workspaces, sqlite DBs, or other bulky artifacts.
- Treat anything under `competitions/**/{public,private,raw,downloads}/` and `runs/` as untracked outputs.

## Benchmark security posture
- Phases 1–5 are “functionality only, not secure”.
- Phase 6 introduces hard enforcement (isolation + egress allowlist + strict mounts).

## Time limits
- Default to short commands with timeouts; avoid long-running jobs unless explicitly requested.
