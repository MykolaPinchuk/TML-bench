# Writer Playbook (Lightweight)

Purpose: help a writer agent produce a credible first full draft from existing evidence.

This is intentionally short. The coordination mechanics are in `docs/paper/PAPER_WORKFLOW.md`.

## Paper audience and scope

- Audience: Industry partitioners, engineers, and researchers are primary audience. Academic researchers and the broader AI/ML community are secondary audience.
- Format: A paper in AI/ML to be put on Arxiv. The paper should not exceed 25 pages including references and appendices.
- The paper should be very clear on why practitioners should care about main results. Academic contributions are secondary. The paper should be accessible to practitioners with a reasonable AI/ML background, not just to academics.

## Output Targets

- Primary output: `docs/paper/draft_vN.md` (from `active_draft` in `docs/paper/PAPER_STATE.md`).
- Evidence pointers: `docs/paper/claims_matrix_vN.md` (from `active_claims` in `docs/paper/PAPER_STATE.md`).
- Evidence inputs: use `active_assets_dir` from `docs/paper/PAPER_STATE.md` for tables/figures.

Do not mention internal workflow terms in the paper (for example “bundle”, “agent”, “paper_assets”, “request”).

## Writing Style (House Rules)

- Avoid “we” unless the paper has multiple authors. Prefer “this paper”. Use “I” rarely.
- Prefer short sentences. One sentence should usually carry one idea.
- Avoid semicolons. Use full stops.
- Avoid dashes. Hyphens are fine.
- Prefer active voice.
- Do not use bold text. Minimize italics.
- Be succinct, specific, and reasonably formal. Avoid throat-clearing expressions. But make sure that reader has enough context. And do not let conciseness disrupt idea flow. Make sure that all logical steps are explained. 
- Use connecting words as needed. They will likely help maintaining idea flow with short sentences. Hence, thus, therefore etc. 
- Do not use "X is Y, not Z" types of sentences. 
- Avoid internal details like versioning.

## Evidence Discipline (Non-Negotiable)

- Every quantitative statement in `active_draft` must have an entry in `active_claims` with an evidence path inside this repo (prefer `active_assets_dir`).
- If you cannot support a quantitative change with existing evidence, stop and file a request (see `docs/paper/PAPER_WORKFLOW.md`).
- Do not “round-trip” numbers through prose. Copy exact values and keep metric direction explicit (AUC higher-better. RMSE lower-better).

## How To Draft (Practical, Not Process-Heavy)

- Start by making the draft readable end-to-end (even if imperfect).
- Prefer a claim-driven structure:
  - State the claim.
  - Point to the supporting figure/table.
  - Give one sentence of interpretation and one sentence of limitation/caveat when needed.
- Use appendices liberally. If a detail is useful but interrupts flow, push it to an appendix section.
- Avoid a comprehensive literature review on draft1. Add later.

## Common Pitfalls To Avoid

- “Model X is best” without specifying the aggregation/normalization and where it’s shown.
- Mixing canonical scope (complete-model 10) with deferred/partial backfill.
- Adding new metrics, datasets, or comparisons not present in `active_assets_dir`.
- Referring to internal ops (“the research agent”, “the workflow”, “the bundle”).

## Optional: PDF/LaTeX

If you decide to produce LaTeX/PDF in this repo, keep build outputs under `tmp/` (ignored) so git diffs stay clean.
Only add committed LaTeX sources if you and the human explicitly agree on the directory layout.

