# TML-bench overview

## What this is
TML-bench is a benchmark + leaderboard for **autonomous tabular ML work** (Kaggle-style) run under a single scaffold (**Kilo**).

The benchmark measures whether a model-driven agent can:
- load tabular data,
- train a model within a fixed budget,
- produce a valid `submission.csv`,
- and achieve a good score on a **private holdout** that is never visible to the agent.

## Why it exists
Many existing “agent benchmarks” test code correctness or synthetic tasks, not end-to-end DS work (data prep → training → submission formatting → iteration). TML-bench aims to be:
- small and cheap to run repeatedly,
- reproducible and auditable,
- focused on tabular tasks,
- and “contamination-resistant enough” by using recent tasks + no browsing + private holdout scoring.

## Phase posture (important)
- **Phases 1–5 are functionality-only (not secure).**
- **Phase 6** introduces hard enforcement (isolation + strict mounts + egress allowlist).

Interpret results accordingly until Phase 6 exists.

## Core protocol (Phase 1)
Per competition we generate:
- `public/train_public.csv` (features + labels)
- `public/test_public.csv` (features only)
- `public/sample_submission.csv`
- `private/holdout_labels.parquet` (labels only; never given to agent)

Policy: `competitions/<id>/prepare_competition.py` is the canonical way to generate `public/` and `private/` (no manual edits).

A run is “successful” when:
- `submission.csv` exists,
- schema matches `sample_submission.csv`,
- row count and IDs match `test_public.csv`,
- scoring completes and returns a numeric metric.

## Where to look in this repo
- `prd.md` — the full PRD and phased plan.
- `docs/plan/v1.md` — low-level design for Phases 1–3.
- `orchestrator/` — Phase 1 core logic (prepare/validate/score).
- `competitions/` — per-competition specs and preparation scripts.
- `HANDOFF.md` — what the next slice is.
