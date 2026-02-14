# Human Cheat Sheet (Paper Workflow)

If you remember nothing else:
- Open `docs/paper/PAPER_STATE.md` to see what is currently active.
- Use the copy/paste prompts below only when switching agents.
- Everything between start/stop prompts is normal freeform chatting.

## What To Check

- `docs/paper/PAPER_STATE.md` (active bundle + what comes next)
- `docs/paper/requests/` (open requests, if any)

## Copy/Paste Prompts

Writer bootstrap (no work yet):

```text
Bootstrap only (no work yet):
- Do not edit any files and do not run commands.
- Read docs/paper/PAPER_WORKFLOW.md and docs/paper/PAPER_STATE.md.
- Reply with:
  1) active_assets_dir / next_assets_dir / active_draft / active_claims as you understand them
  2) 3–7 bullet summary of the workflow constraints
  3) any questions/risks you see
Stop after that.
```

Writer stop/handoff:

```text
Stop/handoff:
- Before stopping, list any new or changed quantitative statements you introduced this session.
- For each one, confirm it has an evidence link in the active claims matrix (active_claims from PAPER_STATE).
- If anything lacks evidence or you need new evidence to proceed, create docs/paper/requests/REQ-YYYYMMDD-XX.md targeting next_assets_dir from PAPER_STATE, then stop.
- If you are not blocked and all quantitative changes are evidenced, stop now (no request needed).
```

Research bootstrap (no work yet):

```text
Bootstrap only (no work yet):
- Do not edit any files and do not run commands.
- Read docs/paper/PAPER_WORKFLOW.md and docs/paper/PAPER_STATE.md.
- If docs/paper/requests/ contains any requests, also read the newest one.
- Reply with:
  1) what you think the next action should be (fulfill request vs produce next frozen bundle)
  2) what you would create/change and where (exact paths, including next_assets_dir if applicable)
  3) any questions/risks you see
Stop after that.
```

Research stop/handoff:

```text
Stop/handoff:
- If you created next_assets_dir, update PAPER_STATE so it becomes active_assets_dir and advance next_assets_dir by 1 version, then stop.
- If you did not create a new bundle, stop now.
```

