# onboarding.md

This file describes how onboarding should work for agents in this repo.

## What the user will do
- Start a new Codex chat.
- Attach `agents.md`.
- Type a single word: `Onboard`.

## What you (the agent) must do on `Onboard`
Follow the onboarding procedure in `repo_workflow.md`:
- Sync agent identity first: parse `AgentNN` from kickoff message and update `agent_logs/current.md` `id:` if stale.
- Read the small set of index/state files first.
- Include `a2a_notes.md` in that initial pass (async reliability guardrails).
- Propose a bounded list (<= 10) of additional files you need next, and open only those.
- Produce the required onboarding output (summary, options, files read, unknowns).
- Append a short entry to `agent_logs/current.md`.
