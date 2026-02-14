---
name: handoff
description: Prepare handoff: update HANDOFF/REPO_MAP, rotate logs, update .gitignore if needed, and create a safe handoff git commit.
---

When invoked, do this in order.

A) Documentation and state (must do)
0) Agent identity check (must do first):
   - Verify `agent_logs/current.md` `id:` matches kickoff `AgentNN` for the current chat.
   - If stale, sync it before any rotation/commit.

1) Update `HANDOFF.md`:
   - Fill/refresh every section.
   - Include concrete evidence: file paths and (if a commit is created) the commit hash.

2) Update `REPO_MAP.md` only if needed:
   - new important file/dir/entrypoint created
   - important file moved/renamed
   - canonical commands/entrypoints changed
   - focus area ("hot paths") changed

3) Ensure `.gitignore` stays strict for competition data, runs, and artifacts.

B) Log rotation (must do)
1) Determine next log filename:
   - `agent_logs/YYYY-MM-DD_agentNN.md`, where `NN` comes from the kickoff-synced `agent_logs/current.md` `id: agentNN`.
   - If that file already exists for today, use `agent_logs/YYYY-MM-DD_agentNN_01.md`, then `_02`, etc.
2) Move `agent_logs/current.md` -> that filename.
3) Append a one-line entry to `agent_logs/INDEX.md`:
   - `- YYYY-MM-DD_agentNN.md — <short summary> (optional: commit <hash>)`
4) Create a fresh `agent_logs/current.md`.

C) Safe handoff commit (must do, unless safety checks fail)
Before committing, always show:
- `git status`
- `git diff --stat`

Never commit competition data, runs, artifacts, or secrets (see `.gitignore`).

Commit message:
- `agentNN: handoff(<area>): <short description>`
- Derive `agentNN` from kickoff-synced `agent_logs/current.md` (field `id:`). If missing/ambiguous, stop and ask the human.
- Choose `<area>` from: `workflow`, `docs`, `orchestrator`, `competitions`, `prompts`, `ci`, `misc`.
