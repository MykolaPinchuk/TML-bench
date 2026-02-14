# Human Cheat Sheet (Repo Workflow)

If you remember nothing else:
- Always include `AgentNN` in the first message of a new agent chat (so the agent can sync `agent_logs/current.md`).
- Put the trigger word on its own line: `Onboard` / `checkpoint` / `handoff` / `wrap up`.
- Read `HANDOFF.md` when deciding what to do next.

## New Chat Kickoff Templates

Research/coder agent:

```text
[TML-bench Agent12 2/14 8am]
Onboard
```

Writer agent:

```text
[TML-bench Agent13 (writer) 2/14 11am]
Onboard
```

Notes:
- `Onboard` is case-insensitive (`onboard` is fine too).
- Use `Agent13 (writer)` rather than special tokens like `Writer_Agent13`; the only important part is that `Agent13` appears.

## Trigger Words

- `Onboard` (any case): deterministic onboarding (reads index files, bounded discovery, writes `agent_logs/current.md`).
- `checkpoint` (use exactly this, lowercase): safe checkpoint commit procedure.
- `handoff` / `wrap up` (any case): wrap-up procedure (handoff docs + log rotation + safe commit).

## Paper Workflow Pointer

When you are doing paper drafting with separate research and writer agent chats:
- Main workflow: `docs/paper/PAPER_WORKFLOW.md`
- State pointer: `docs/paper/PAPER_STATE.md`
- Paper-specific prompts: `docs/paper/HUMAN_CHEATSHEET.md`

## One-Line “What Next?”

- If you are unsure what the project is doing right now: open `HANDOFF.md`.

