# a2a_writer_notes.md (paper-facing writer guidance)

This file captures recurring feedback for writer agents working on `docs/paper/draft_v1.md`.

## Reader-first (external audience)

- Assume the reader knows *nothing* about internal repo processes, internal naming, or how results were produced.
- Do not mention internal counters/IDs in the paper text (examples: `sources_found=…`, “missing_cells”, “profiled1”, “Result 0.5”, “PRD phase”).
- Avoid jargon that only makes sense inside this repo (for example, “cells”). Use plain terms like “task×budget setting”, “run”, “median of five runs”.
- The Abstract must be self-contained: define the benchmark at a high level, state what was evaluated, and summarize the main findings. No internal terms, no “evidence base” talk.

## What the reader wants

- What was evaluated: tasks, time budgets, number of models, repeated runs, and what “success” means.
- What was found: headline winners, reliability differences, stability differences, and how performance changes with more time.
- How to use it: practical takeaways (for example, “reliability varies even among top performers”).

## Kilo Code / harness guidance

- In the main text, keep the harness description short (1–3 sentences). Point to an appendix for details.
- In the appendix, explain:
  - what Kilo Code is,
  - why we standardize on one harness (reduce harness effects),
  - why this harness was chosen (reliability, breadth, ease of sanity checks),
  - and any limitations (results are harness-dependent).
- Always call it “Kilo Code” (never “Kilo”).
- Any “most used / ranking” claims must be dated (“accessed YYYY-MM-DD”) and backed by a public source.

## Scope hygiene

- Do not mention deferred models or “models we plan to run later”. The paper should only discuss the models actually included.
- Do not include internal tables/figures/filenames in the narrative (“result3_…png”, etc.). Use reader-friendly captions and stable names.

## Evidence discipline (internal, but important)

- Keep `docs/paper/claims_matrix_v1.md` aligned with any quantitative or ranking claims you add/change.
- If you add new quantitative claims from web sources (for example, OpenRouter rankings), include the URL and access date in the claim matrix.

## TeX sync

- Keep `docs/paper/tex_v1/` in sync with the Markdown draft and ensure `pdflatex` builds to `tmp/paper_build/main.pdf`.
