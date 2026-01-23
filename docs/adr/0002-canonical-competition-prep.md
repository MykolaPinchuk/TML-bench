# ADR 0002 — Canonical competition preparation

## Context
Benchmark integrity and reproducibility depend on generating the same agent-visible inputs (`public/`) and private holdout labels (`private/`) in a deterministic, auditable way.

## Decision
For each competition `competitions/<id>/`:
- `prepare_competition.py` is the **only** supported way to generate `public/` and `private/`.
- `public/` and `private/` are treated as **generated artifacts**:
  - they are gitignored
  - they must not be edited by hand
- Split behavior is controlled by `spec.yaml` (seed + strategy) and must be reproducible.

## Consequences
- Runs are comparable across time/machines as long as the same `spec.yaml` and raw inputs are used.
- If the split protocol changes, it must be done by changing `spec.yaml` (and ideally recording that change in git).
- Ad-hoc/manual preparation is unsupported because it introduces silent drift and makes results hard to audit.

