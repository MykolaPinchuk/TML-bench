# HANDOFF

## Current slice
v7 post-arXiv improvement planning is now active. Focus is a moderate-effort paper upgrade pass, starting with a simple AutoML/AutoGluon baseline and tightly scoped manuscript updates.

## Current state (2026-03-08)
- Branch state:
  - active branch: `v7`
  - base commit: `e5c82b9` (`Merge pull request #12 from MykolaPinchuk/v6.5`)
- Publication state:
  - first paper version is published on arXiv
  - arXiv link is merged into `master` (`52ef1da`)
- Paper artifacts:
  - markdown draft: `docs/paper/draft_v1.md`
  - claims matrix: `docs/paper/claims_matrix_v1.md`
  - LaTeX entrypoint: `docs/paper/tex_v1/main.tex`
  - latest local build artifact: `tmp/paper_build/main.pdf`
- Planning:
  - v7 plan: `docs/plan/v7.md`

## Immediate next plan (v7 kickoff)
1. Implement a simple reproducible AutoGluon baseline path in baseline tooling.
2. Run it on paper competitions and capture evidence artifacts.
3. Integrate baseline outputs into reporting surfaces used by the paper.
4. Update draft + LaTeX + claims matrix for any new quantitative claims.
5. Rebuild PDF and perform consistency check.

## Deferred unless explicitly requested
- Large benchmark redesign or scope expansion beyond moderate post-arXiv improvements.
- Full canonical policy overhaul.
- Security-hardening track changes unrelated to paper-upgrade goals.

## Key evidence and workflow paths
- Canonical results snapshot: `results.md`
- Canonical stability companion: `docs/reports/v5_5_canonical10_stability.md`
- Paper workflow/state:
  - `docs/paper/PAPER_WORKFLOW.md`
  - `docs/paper/PAPER_STATE.md`
  - `docs/paper/HUMAN_CHEATSHEET.md`
  - `docs/paper/WRITER_PLAYBOOK.md`
- Main paper sources:
  - `docs/paper/draft_v1.md`
  - `docs/paper/claims_matrix_v1.md`
  - `docs/paper/tex_v1/main.tex`
- v7 planning:
  - `docs/plan/v7.md`

## Invariants
- Never commit datasets, run artifacts, sqlite DBs, or secrets.
- Keep claims-to-evidence discipline strict (`docs/paper/claims_matrix_v1.md`).
- Keep `profiled1` canonical reporting policy intact unless user explicitly changes it.

### Human notes

Posisble things for the next steps:
- build some nonagentic baseline like AutoML or smth.
- Add 3 more cheap models using OR API:
-- grok4.1fast
-- mimo v2-flash
-- gemini 3.1 flash0lite

