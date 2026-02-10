# v5.5 Closeout Plan

## Goal
Close v5.5 with a publishable, reproducible, low-noise baseline report centered on the complete 10-model set under `profiled1`, while keeping the 14-model expansion as a separate deferred track.

## Current Baseline (as of 2026-02-10)
- Canonical reporting scope: 10 complete models (`12/12` cells each at 5 successful runs/cell).
- Remaining 4 models are underfilled due to timeout-heavy behavior and circuit-breaker deferrals.
- `results.md` is streamlined and points legacy/transitional content to `docs/archive/results_legacy_snapshots_2026-02-10.md`.

## Non-goals (v5.5)
- Do not broaden canonical leaderboard to partial 14-model coverage.
- Do not introduce new benchmark tasks, new strategy families, or v6 security architecture in this slice.

## Workstreams

### WS1: Reproducibility Lock (P0)
Deliverables:
- Add a deterministic checker that validates canonical 10-model coverage from DB sources (`10 complete models`, `0 underfilled cells in canonical scope`).
- Add a one-command regenerate+verify flow for `results.md`.

Acceptance:
- Running the flow on current local DBs reproduces the same coverage snapshot shown in `results.md`.
- Checker fails loudly if canonical coverage regresses.

### WS2: Reporting Quality Add-ons (P1)
Deliverables:
- Add a concise supplementary block (or companion artifact) for run-count and stability context per model/profile (for example: success counts, median + spread) without expanding canonical model scope.
- Keep main table footprint stable and readable.

Acceptance:
- No duplicate historical sections in `results.md`.
- Canonical table remains complete-model-only.

### WS3: State Hygiene and Handoff Accuracy (P0)
Deliverables:
- Keep `HANDOFF.md` aligned with actual run state and current plan.
- Keep `REPO_MAP.md` pointers current for the closeout workflow.

Acceptance:
- No stale "active run" claims when run is terminal.
- Next agent can continue from `HANDOFF.md` and this plan doc without repo-wide rediscovery.

### WS4: Deferred 14-model Expansion Gate (P2)
Deliverables:
- Keep a small status block with remaining gaps by model/profile.
- Define explicit retry gate: only run expansion passes after circuit-breaker windows clear and provider health is acceptable.

Acceptance:
- Expansion activity does not alter canonical 10-model interpretation until full 14-model completion criteria are met.

## Exit Criteria for v5.5
- Canonical 10-model tables are reproducible by script and pass coverage checks.
- Reporting policy is explicit and enforced in docs.
- Remaining 4-model expansion is clearly marked deferred with concrete restart criteria.
- Handoff docs are accurate at commit time.

## First Execution Order
1. Implement reproducibility checker and regeneration guard.
2. Add compact stability/context supplement.
3. Refresh `HANDOFF.md` with latest terminal run and deferred expansion gate.
4. Checkpoint after each coherent milestone.
