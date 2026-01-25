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

Operational assumption (current workflow): for Chutes and NanoGPT runs, treat cost as a non-constraint (high daily included limits) and optimize for iteration speed.

## Phase posture (important)
- **Phases 1–5 are functionality-only (not secure).**
- **Phase 6** introduces hard enforcement (isolation + strict mounts + egress allowlist).

Interpret results accordingly until Phase 6 exists.

## Manual agent runs (Phase 2)
In Phase 2, the agent is run manually (VSCode + Kilo) in a per-run workspace:
- `python -m orchestrator.run_one create --competition-id <id>` creates `runs/<run_id>/workspace/`
- you run Kilo inside that workspace and produce `submission.csv`
- `python -m orchestrator.run_one finalize --competition-id <id> --run-id <run_id>` validates, scores (private holdout), and records results

## Headless sweeps (Phase 3+)
Use `orchestrator.sweep` to run many models headlessly via Kilo CLI:
- Simple baseline (fast/cheap): `--profile simple-baseline` (240s) and default `--concurrency 4`
- Good baseline (more effort): `--profile good-baseline` (600s) and default `--concurrency 4`

Example:
- `python -m orchestrator.sweep --competition-id playground-series-s6e1 --models-path orchestrator/model_sets/v3_fast.json --profile simple-baseline`

## Audit trail (what proves an agent actually ran)

For any run `runs/<run_id>/`:
- `runs/<run_id>/workspace/` contains the concrete artifacts the agent produced/edited (e.g. `train_model.py`, `submission.csv`).
- `runs/<run_id>/result.json` contains the final private-holdout score plus `submission_sha256` (when recorded) so you can detect identical submissions across “different” runs/models.
- Phase 3 (headless Kilo CLI) additionally writes `runs/<run_id>/artifacts/kilo_stdout.clean.jsonl`, which is Kilo’s JSON event stream (API request events, tool calls, and command outputs).
- To rebuild the leaderboard from `runs/*/result.json` on disk: `python -m orchestrator.leaderboard --import-results --write-root`.

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
