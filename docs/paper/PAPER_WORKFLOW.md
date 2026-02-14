# Paper Drafting Workflow (Single-Repo, Lightweight)

This repo supports a simple research-to-writing loop without a separate “writer repo”.

Principle: agents do not “message” each other; they hand off via repo files.

Human ergonomics goal: you should not need to look up commit hashes or pass them around.

Mechanism: a single “state pointer” file tells every agent what the current active bundle is.

## Minimal Human Prompts (Recommended)

These are intended to be copy/pasted with minimal editing.

Key idea: boilerplate is only for **session boundaries**:
1) a bootstrap prompt immediately after you switch to an agent (no work yet), and
2) a stop/handoff prompt right before you switch away.

Everything in between can be fully freeform: you can iterate with the writer agent however you like (edits, rewrites,
structure changes, tone, LaTeX build tasks), without remembering any workflow details.

Everything “structured” lives in this doc + `docs/paper/PAPER_STATE.md`.

### Writer Agent Session (Bootstrap / Stop)

Writer bootstrap (paste once immediately after switching to the writer agent; do not include any work request):

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

Writer stop/handoff (paste once right before switching away from the writer agent):

```text
Stop/handoff:
- Before stopping, list any new or changed quantitative statements you introduced this session.
- For each one, confirm it has an evidence link in the active claims matrix (active_claims from PAPER_STATE).
- If anything lacks evidence or you need new evidence to proceed, create docs/paper/requests/REQ-YYYYMMDD-XX.md targeting next_assets_dir from PAPER_STATE, then stop.
- If you are not blocked and all quantitative changes are evidenced, stop now (no request needed).
```

### Research Agent Session (Bootstrap / Stop)

Research bootstrap (paste once immediately after switching to the research agent; do not include any work request):

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

Research stop/handoff (paste once right before switching away from the research agent):

```text
Stop/handoff:
- If you created next_assets_dir, update PAPER_STATE so it becomes active_assets_dir and advance next_assets_dir by 1 version, then stop.
- If you did not create a new bundle, stop now.
```

## Single Source Of Truth: `PAPER_STATE.md`

Use `docs/paper/PAPER_STATE.md` as the one file every agent reads first.

It should contain, at minimum:
- which evidence bundle is active (the directory name),
- which draft/claims files are active,
- which version to create next when producing new evidence.

Example contents (illustrative):

```md
# PAPER_STATE

active_assets_dir: docs/paper/paper_assets_v1
next_assets_dir: docs/paper/paper_assets_v2
active_draft: docs/paper/draft_v1.md
active_claims: docs/paper/claims_matrix_v1.md
```

## Roles

`Research agent` responsibilities:
- Run analysis/code to generate or update evidence.
- Produce a frozen, versioned evidence bundle: `docs/paper/paper_assets_vN/`.
- If evidence changes are needed later, create the next bundle (from `next_assets_dir`) and update `PAPER_STATE.md`.
- Never overwrite an existing bundle in place.

`Writer agent` responsibilities:
- Write the manuscript: `docs/paper/draft_vN.md`.
- Maintain claim-to-evidence traceability: `docs/paper/claims_matrix_vN.md`.
- When blocked on missing evidence, write a request file under `docs/paper/requests/`.
- Always use `active_assets_dir` from `PAPER_STATE.md` as the evidence source.

## File Contract (The “Interface”)

Evidence inputs (produced by research, treated as read-only by writer):
- `docs/paper/paper_assets_vN/`
- `results.md`
- `docs/reports/` (stability/variance supplements)
- `docs/paper/figures/` (if used as the upstream for assets)

Writing surfaces (produced by writer):
- `docs/paper/draft_vN.md`
- `docs/paper/claims_matrix_vN.md`
- `docs/paper/requests/REQ-*.md`

Build outputs (writer runs code, but outputs should be ignored/uncommitted):
- Put LaTeX/PDF build artifacts under `tmp/` (or another ignored directory) to avoid noisy diffs.

## Freeze Boundary (Minimal Enforcement)

Each handoff is a commit boundary, but humans do not pass hashes around.

Research “freeze” for version `vN` means:
- Verify canonical evidence (for current baseline, this is the `profiled1` canonical flow).
- Materialize a self-contained bundle in `docs/paper/paper_assets_vN/`.
- Commit the result.

Writer always starts from whatever `PAPER_STATE.md` says is active.

## Requests As Files (No Copy/Paste Between Chats)

When the writer needs more evidence, they create a request file:
- Path: `docs/paper/requests/REQ-YYYYMMDD-XX.md`
- Purpose: specify exactly what research should generate and where it should land in `next_assets_dir` (from `PAPER_STATE.md`).

Minimal request template:

```md
# REQ-YYYYMMDD-XX: <short title>

Active assets dir: <copy from PAPER_STATE.md>
Next assets dir: <copy from PAPER_STATE.md>

Need:
- <what evidence is missing / what decision it unblocks>

Acceptance criteria:
- Output path(s): <next assets dir>/<...>
- Regeneration command(s): <command(s) research should run>
- Claim IDs affected: C<...> (or “new claim IDs needed”)
```

Research fulfills by:
- Creating the next assets dir (from `PAPER_STATE.md`) with the requested assets.
- Updating any evidence pointers needed in `docs/paper/claims_matrix_vN.md` (or documenting what the writer must update).
- Replying in the request file with evidence paths and any important regeneration notes.
- Updating `PAPER_STATE.md` so the new bundle becomes active and `next_assets_dir` advances.

## Human Walkthrough Example

Goal: produce the first full draft from the canonical 10-model evidence.

### Example: Exact Human Messages

This is the full loop where you keep two VS Code Codex chats open (one research, one writer) but only interact with one at a time.

Assume `docs/paper/PAPER_STATE.md` currently points to:
- `active_assets_dir: docs/paper/paper_assets_v1`
- `next_assets_dir: docs/paper/paper_assets_v2`

1. Research agent (example: agent12): bootstrap (no work)

```text
Bootstrap only (no work yet):
- Do not edit any files and do not run commands.
- Read docs/paper/PAPER_WORKFLOW.md and docs/paper/PAPER_STATE.md.
- If docs/paper/requests/ contains any requests, also read the newest one.
- Reply with your proposed next action and exact paths you will touch.
Stop after that.
```

2. You then give the research agent a normal work request (freeform)

Example (your wording can be anything):

```text
Proceed: produce the next frozen evidence bundle per PAPER_WORKFLOW. If you need to change evidence, write it into next_assets_dir and advance PAPER_STATE.
```

3. Writer agent (example: agent13_writer): bootstrap (no work)

```text
Bootstrap only (no work yet):
- Do not edit any files and do not run commands.
- Read docs/paper/PAPER_WORKFLOW.md and docs/paper/PAPER_STATE.md.
- Reply with your understanding of the active bundle and constraints.
Stop after that.
```

4. You then iterate with the writer agent normally (freeform)

Example (your wording can be anything):

```text
Proceed: turn docs/paper/draft_v1.md into a coherent first full draft using active_assets_dir as evidence, and keep claims_matrix consistent.
```

5. Writer creates a request when blocked (example)

`docs/paper/requests/REQ-20260214-01.md`:
- describes what’s missing,
- specifies output under `next_assets_dir` (e.g. `docs/paper/paper_assets_v2/tables/...`),
- names the affected Claim IDs (or says new IDs are needed).

6. You switch to the research agent and ask it to fulfill the newest request

```text
Proceed: fulfill the newest request under docs/paper/requests/ into next_assets_dir, then advance PAPER_STATE.
```

7. You switch back to the writer agent and continue iterating

```text
Proceed: continue drafting using the newly active_assets_dir and update the claims matrix accordingly.
```

This loop repeats until draft quality is acceptable.
