#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from update_profiled1_fiverun_tables import AUTO_END, AUTO_START, COMPETITIONS, PROFILES, SOURCE_DBS


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_MD = REPO_ROOT / "results.md"
TARGET_RUNS_PER_CELL = 5

# Canonical frozen set for v5.5 closeout.
CANONICAL_MODELS: list[tuple[str, str]] = [
    ("chutes", "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8"),
    ("chutes", "openai/gpt-oss-120b-TEE"),
    ("chutes", "zai-org/GLM-4.7-FP8"),
    ("chutes", "zai-org/GLM-4.7-Flash"),
    ("chutes", "MiniMaxAI/MiniMax-M2.1-TEE"),
    ("chutes", "zai-org/GLM-4.6-FP8"),
    ("chutes", "deepseek-ai/DeepSeek-V3.1-Terminus"),
    ("chutes", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"),
    ("chutes", "mistralai/Devstral-2-123B-Instruct-2512-TEE"),
    ("chutes", "tngtech/DeepSeek-TNG-R1T2-Chimera"),
]


@dataclass(frozen=True)
class RunRow:
    run_id: str
    created_at: str
    competition_id: str
    prompt_profile: str
    budget_time_seconds: int
    provider: str
    model_id: str
    score_raw: float


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(r[1]) for r in cur.fetchall()}


def _load_success_runs(db_path: Path) -> Iterable[RunRow]:
    con = sqlite3.connect(db_path)
    try:
        cols = _table_columns(con, "runs")
        has_prompt_strategy = "prompt_strategy" in cols
        cur = con.cursor()
        if has_prompt_strategy:
            cur.execute(
                """
                SELECT run_id, created_at, competition_id, prompt_profile, budget_time_seconds,
                       provider, model_id, score_raw, prompt_strategy
                FROM runs
                WHERE status='success'
                """
            )
            for run_id, created_at, comp, profile, budget, provider, model_id, score_raw, prompt_strategy in cur.fetchall():
                if prompt_strategy not in ("profiled1", None, ""):
                    continue
                if score_raw is None:
                    continue
                yield RunRow(
                    run_id=str(run_id or "").strip(),
                    created_at=str(created_at or ""),
                    competition_id=str(comp or "").strip(),
                    prompt_profile=str(profile or "").strip(),
                    budget_time_seconds=int(budget or 0),
                    provider=str(provider or "").strip(),
                    model_id=str(model_id or "").strip(),
                    score_raw=float(score_raw),
                )
        else:
            cur.execute(
                """
                SELECT run_id, created_at, competition_id, prompt_profile, budget_time_seconds,
                       provider, model_id, score_raw
                FROM runs
                WHERE status='success'
                """
            )
            for run_id, created_at, comp, profile, budget, provider, model_id, score_raw in cur.fetchall():
                if score_raw is None:
                    continue
                yield RunRow(
                    run_id=str(run_id or "").strip(),
                    created_at=str(created_at or ""),
                    competition_id=str(comp or "").strip(),
                    prompt_profile=str(profile or "").strip(),
                    budget_time_seconds=int(budget or 0),
                    provider=str(provider or "").strip(),
                    model_id=str(model_id or "").strip(),
                    score_raw=float(score_raw),
                )
    finally:
        con.close()


def _collect_counts() -> tuple[dict[tuple[str, str, int, str, str], int], list[Path]]:
    counts: dict[tuple[str, str, int, str, str], int] = defaultdict(int)
    seen_global: set[tuple[str, str]] = set()
    comp_ids = {c for c, _, _ in COMPETITIONS}
    profile_budgets = set(PROFILES)
    model_set = set(CANONICAL_MODELS)
    sources: list[Path] = []

    for rel in SOURCE_DBS:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        sources.append(src)
        for row in _load_success_runs(src):
            if row.competition_id not in comp_ids:
                continue
            if (row.prompt_profile, row.budget_time_seconds) not in profile_budgets:
                continue
            if (row.provider, row.model_id) not in model_set:
                continue
            if row.run_id:
                dedupe_key = ("run_id", row.run_id)
            else:
                dedupe_key = (
                    "fp",
                    (
                        f"{src.name}:{row.created_at}:{row.competition_id}:{row.prompt_profile}:"
                        f"{row.budget_time_seconds}:{row.provider}:{row.model_id}:{row.score_raw:.12g}"
                    ),
                )
            if dedupe_key in seen_global:
                continue
            seen_global.add(dedupe_key)
            counts[(row.competition_id, row.prompt_profile, row.budget_time_seconds, row.provider, row.model_id)] += 1
    return counts, sources


def _extract_results_md_signals() -> tuple[int | None, set[str]]:
    text = RESULTS_MD.read_text(encoding="utf-8")
    start = text.find(AUTO_START)
    end = text.find(AUTO_END)
    if start < 0 or end < 0 or end < start:
        raise RuntimeError("Could not find AUTO block markers in results.md")

    block = text[start:end]
    m = re.search(r"Coverage snapshot:\s*\*\*(\d+)\s+models\*\*", block)
    declared_coverage = int(m.group(1)) if m else None

    model_ids: set[str] = set()
    if "Complete models in scope:" in block:
        lines = block.splitlines()
        i = lines.index("Complete models in scope:")
        for ln in lines[i + 1 :]:
            if not ln.strip():
                break
            if ln.startswith("- `") and ln.endswith("`"):
                model_ids.add(ln[3:-1])
    return declared_coverage, model_ids


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate canonical v5.5 profiled1 10-model coverage and results.md metadata."
    )
    ap.add_argument("--json", action="store_true", help="Print machine-readable summary JSON.")
    args = ap.parse_args()

    counts, sources = _collect_counts()
    missing_cells: list[dict[str, object]] = []
    for provider, model_id in CANONICAL_MODELS:
        for comp, _, _ in COMPETITIONS:
            for profile, budget in PROFILES:
                have = counts.get((comp, profile, budget, provider, model_id), 0)
                need = max(0, TARGET_RUNS_PER_CELL - have)
                if need:
                    missing_cells.append(
                        {
                            "provider": provider,
                            "model_id": model_id,
                            "competition_id": comp,
                            "profile": profile,
                            "budget_seconds": budget,
                            "have": have,
                            "need": need,
                        }
                    )

    declared_coverage, declared_models = _extract_results_md_signals()
    expected_model_ids = {m for _, m in CANONICAL_MODELS}

    errors: list[str] = []
    if len(sources) != len(SOURCE_DBS):
        missing_sources = [rel for rel in SOURCE_DBS if not (REPO_ROOT / rel).exists()]
        errors.append(f"Missing source DB files: {missing_sources}")
    if missing_cells:
        errors.append(f"Canonical set has underfilled cells: {len(missing_cells)}")
    if declared_coverage != len(CANONICAL_MODELS):
        errors.append(
            "results.md coverage snapshot mismatch: "
            f"declared={declared_coverage}, expected={len(CANONICAL_MODELS)}"
        )
    if declared_models != expected_model_ids:
        errors.append("results.md complete-model list does not match canonical 10-model set")

    summary = {
        "ok": not errors,
        "sources_found": len(sources),
        "sources_expected": len(SOURCE_DBS),
        "canonical_models_expected": len(CANONICAL_MODELS),
        "missing_cells": missing_cells,
        "results_md_declared_coverage": declared_coverage,
        "results_md_declared_models_count": len(declared_models),
        "errors": errors,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"sources_found={len(sources)}/{len(SOURCE_DBS)}")
        print(f"canonical_models={len(CANONICAL_MODELS)}")
        print(f"missing_cells={len(missing_cells)}")
        print(f"results_md_declared_coverage={declared_coverage}")
        print(f"results_md_declared_models={len(declared_models)}")
        if errors:
            print("status=FAILED")
            for err in errors:
                print(f"error: {err}")
            if missing_cells:
                print("first_missing_cell:", missing_cells[0])
        else:
            print("status=OK")

    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
