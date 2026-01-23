# HANDOFF

## Current slice
v0 (setup): establish the agentic workflow scaffolding and guardrails for TML-bench.

## Invariants (do not break)
- No secrets or credentials in git.
- No Kaggle datasets / generated competition data in git.
- No run artifacts (submissions, transcripts, workspaces) in git.
- Phase branches: work progresses on `v0`, then `v1`, `v2`, ... (human pushes).

## State of work

### Done (with evidence)
- PRD exists: `prd.md`.
- Agentic workflow scaffolding (this set of files): `repo_workflow.md`, `onboarding.md`, `HANDOFF.md`, `REPO_MAP.md`, `agent_logs/`.

### Next (ordered)
1) Create branch `v1` (Phase 1) and write LLD for prepare/validate/score contracts.
2) Implement Phase 1 scaffolding (competition spec + deterministic split + validator + scorer).

### Open questions
- None yet (blocked on selecting the first competition/task for Phase 1).

## Repro / smoke check
- Commands run:
  - `git status -sb`
- Outcome:
  - Repo is in setup phase; no code executed yet.

## Known issues / current breakage
- None known.

## Git notes (handoff)
- `.gitignore` updates made:
  - Ignore competition data, runs, and sqlite DBs; allow small leaderboard outputs under `results/`.
