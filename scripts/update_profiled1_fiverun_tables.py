#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_MD = REPO_ROOT / "results.md"
AUTO_START = "<!-- AUTO:PROFILED1_FIVERUN_START -->"
AUTO_END = "<!-- AUTO:PROFILED1_FIVERUN_END -->"

SOURCE_DBS = [
    "results/results_v5_5_v3fast_profiled1_r2.sqlite",
    "results/results_v5_5_working6_suite.sqlite",
    "results/results_v5_5_working6_profiled1_rep2.sqlite",
    "results/results_v5_5_user_selected3_r2_v2.sqlite",
    "results/results_v5_5_qwen_topup3.sqlite",
    "results/results_v5_5_topup3models_r5.sqlite",
    "results/results_v5_5_topup6_waveA_r5_seeded.sqlite",
    "results/results_v5_5_topup3_waveB_r5_seeded.sqlite",
]

COMPETITIONS: list[tuple[str, str, str]] = [
    ("bank-customer-churn-ict-u-ai", "AUC", "higher is better"),
    ("foot-traffic-wuerzburg-retail-forecasting-2-0", "RMSE", "lower is better"),
    ("playground-series-s5e10", "RMSE", "lower is better"),
    ("playground-series-s6e1", "RMSE", "lower is better"),
]
PROFILES: list[tuple[str, int]] = [
    ("simple-baseline", 240),
    ("good-baseline", 600),
    ("sota-xgb", 1200),
]

MODEL_ORDER = [
    "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
    "openai/gpt-oss-120b-TEE",
    "zai-org/GLM-4.7-FP8",
    "zai-org/GLM-4.7-Flash",
    "MiniMaxAI/MiniMax-M2.1-TEE",
    "zai-org/GLM-4.6-FP8",
    "deepseek-ai/DeepSeek-V3.1-Terminus",
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
]

MODEL_LABELS = {
    "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8": "Qwen3-Coder-480B-A35B",
    "openai/gpt-oss-120b-TEE": "GPT OSS 120B TEE",
    "zai-org/GLM-4.7-FP8": "GLM-4.7-FP8",
    "zai-org/GLM-4.7-Flash": "GLM 4.7 Flash",
    "MiniMaxAI/MiniMax-M2.1-TEE": "MiniMax-M2.1-TEE",
    "zai-org/GLM-4.6-FP8": "GLM-4.6-FP8",
    "deepseek-ai/DeepSeek-V3.1-Terminus": "DeepSeek-V3.1-Terminus",
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16": "NVIDIA-Nemotron-3-Nano",
}


def _parse_iso(ts: str | None) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _existing_sources() -> list[Path]:
    out: list[Path] = []
    for rel in SOURCE_DBS:
        p = REPO_ROOT / rel
        if p.exists():
            out.append(p)
    return out


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(r[1]) for r in cur.fetchall()}


def _load_success_runs(
    db_path: Path,
) -> Iterable[tuple[str, datetime, str, str, int, str, str, float]]:
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
                yield (
                    str(run_id or "").strip(),
                    _parse_iso(str(created_at or "")),
                    str(comp or ""),
                    str(profile or ""),
                    int(budget or 0),
                    str(provider or ""),
                    str(model_id or ""),
                    float(score_raw),
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
                yield (
                    str(run_id or "").strip(),
                    _parse_iso(str(created_at or "")),
                    str(comp or ""),
                    str(profile or ""),
                    int(budget or 0),
                    str(provider or ""),
                    str(model_id or ""),
                    float(score_raw),
                )
    finally:
        con.close()


def _render_tables() -> str:
    comp_ids = {c for c, _, _ in COMPETITIONS}
    profile_budgets = set(PROFILES)
    by_cell: dict[tuple[str, str, int, str, str], list[tuple[datetime, str, float]]] = defaultdict(list)
    seen_global: set[tuple[str, str]] = set()
    all_models: set[str] = set()
    sources = _existing_sources()

    for src in sources:
        for run_id, created_at, comp, profile, budget, provider, model_id, score_raw in _load_success_runs(src):
            if provider != "chutes":
                continue
            if comp not in comp_ids:
                continue
            if (profile, budget) not in profile_budgets:
                continue
            if run_id:
                dedupe_key = ("run_id", run_id)
            else:
                dedupe_key = (
                    "fp",
                    f"{src.name}:{created_at.isoformat()}:{comp}:{profile}:{budget}:{provider}:{model_id}:{score_raw:.12g}",
                )
            if dedupe_key in seen_global:
                continue
            seen_global.add(dedupe_key)
            all_models.add(model_id)
            by_cell[(comp, profile, budget, provider, model_id)].append((created_at, run_id, score_raw))

    complete_models: list[str] = []
    for model_id in sorted(all_models):
        ok = True
        for comp, _, _ in COMPETITIONS:
            for profile, budget in PROFILES:
                runs = by_cell.get((comp, profile, budget, "chutes", model_id), [])
                if len(runs) < 5:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            complete_models.append(model_id)

    # Stable preferred order first, then any additional complete models.
    ordered_models = [m for m in MODEL_ORDER if m in complete_models]
    for m in sorted(complete_models):
        if m not in ordered_models:
            ordered_models.append(m)

    medians: dict[tuple[str, str, int, str], float] = {}
    for comp, _, _ in COMPETITIONS:
        for profile, budget in PROFILES:
            for model_id in ordered_models:
                runs = by_cell[(comp, profile, budget, "chutes", model_id)]
                first_five = sorted(runs, key=lambda x: (x[0], x[1]))[:5]
                medians[(comp, profile, budget, model_id)] = float(median([x[2] for x in first_five]))

    lines: list[str] = []
    lines.append("### 0.1) Dedicated 5-run median tables (auto-updated; complete models only)")
    lines.append("")
    lines.append("Method:")
    lines.append("- For each `(competition, model, profile)` cell, take the earliest 5 successful `profiled1` runs by `created_at` and compute median `score_raw`.")
    lines.append("- Include only models with full `12/12` cells at 5 runs.")
    lines.append("")
    lines.append(f"Coverage snapshot: **{len(ordered_models)} models** currently satisfy the 5-run criterion.")
    lines.append("")
    lines.append("Source DBs used:")
    for src in sources:
        lines.append(f"- `{src.relative_to(REPO_ROOT)}`")
    lines.append("")
    lines.append("Complete models in scope:")
    for m in ordered_models:
        lines.append(f"- `{m}`")
    lines.append("")

    for comp, metric, direction in COMPETITIONS:
        lines.append(f"### {comp} ({metric}; {direction})")
        lines.append("")
        headers = ["profile"] + [MODEL_LABELS.get(m, m) for m in ordered_models]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] + ["---:" for _ in ordered_models]) + "|")
        for profile, budget in PROFILES:
            row_name = f"{profile} ({budget}s)"
            vals = [f"{medians[(comp, profile, budget, m)]:.6f}" for m in ordered_models]
            lines.append("| " + " | ".join([row_name] + vals) + " |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _update_results_md(block: str) -> None:
    text = RESULTS_MD.read_text(encoding="utf-8")
    start = text.find(AUTO_START)
    end = text.find(AUTO_END)
    if start < 0 or end < 0 or end < start:
        raise RuntimeError("Could not find AUTO markers in results.md")
    start_block = start + len(AUTO_START)
    replacement = "\n\n" + block + "\n"
    new_text = text[:start_block] + replacement + text[end:]
    RESULTS_MD.write_text(new_text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Update 5-run-only profiled1 tables in results.md.")
    ap.add_argument("--check", action="store_true", help="Print block to stdout instead of updating file.")
    args = ap.parse_args()

    block = _render_tables()
    if args.check:
        print(block, end="")
        return 0

    _update_results_md(block)
    print(f"updated: {RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
