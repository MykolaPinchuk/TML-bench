#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from check_profiled1_canonical_coverage import CANONICAL_MODELS, _load_success_runs
from update_profiled1_fiverun_tables import COMPETITIONS, MODEL_LABELS, PROFILES, SOURCE_DBS


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "docs" / "reports" / "v5_5_canonical10_stability.md"
TARGET_RUNS = 5


@dataclass(frozen=True)
class CellSeries:
    model_id: str
    values: list[float]


def _parse_created_at(text: str) -> datetime:
    raw = (text or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = datetime.min
    return dt


def _collect_first_five() -> dict[tuple[str, str, int, str], CellSeries]:
    comp_ids = {c for c, _, _ in COMPETITIONS}
    profile_budgets = set(PROFILES)
    canonical = set(CANONICAL_MODELS)

    by_cell: dict[tuple[str, str, int, str], list[tuple[datetime, str, float]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for rel in SOURCE_DBS:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        for row in _load_success_runs(src):
            if row.competition_id not in comp_ids:
                continue
            if (row.prompt_profile, row.budget_time_seconds) not in profile_budgets:
                continue
            if (row.provider, row.model_id) not in canonical:
                continue
            if row.run_id:
                dkey = ("run_id", row.run_id)
            else:
                dkey = (
                    "fp",
                    (
                        f"{src.name}:{row.created_at}:{row.competition_id}:{row.prompt_profile}:"
                        f"{row.budget_time_seconds}:{row.provider}:{row.model_id}:{row.score_raw:.12g}"
                    ),
                )
            if dkey in seen:
                continue
            seen.add(dkey)
            key = (row.competition_id, row.prompt_profile, row.budget_time_seconds, row.model_id)
            by_cell[key].append((_parse_created_at(row.created_at), row.run_id, row.score_raw))

    out: dict[tuple[str, str, int, str], CellSeries] = {}
    for key, vals in by_cell.items():
        first_five = sorted(vals, key=lambda x: (x[0], x[1]))[:TARGET_RUNS]
        if len(first_five) < TARGET_RUNS:
            continue
        out[key] = CellSeries(model_id=key[3], values=[v for _, _, v in first_five])
    return out


def _fmt_stats(values: list[float]) -> str:
    med = statistics.median(values)
    sorted_vals = sorted(values)
    q1 = sorted_vals[1]
    q3 = sorted_vals[3]
    return f"{med:.6f} ({q1:.6f}..{q3:.6f})"


def _render() -> str:
    series = _collect_first_five()
    model_ids = [m for _, m in CANONICAL_MODELS]

    lines: list[str] = []
    lines.append("# v5.5 Canonical10 Stability Supplement")
    lines.append("")
    lines.append("This companion report summarizes variability for the canonical 10-model set.")
    lines.append("")
    lines.append("Method:")
    lines.append("- Strategy: `profiled1`.")
    lines.append("- For each `(competition, model, profile)`, use the earliest 5 successful runs (same rule as canonical table).")
    lines.append("- Cell value format: `median (Q1..Q3)` on `score_raw`.")
    lines.append("")

    for comp, metric, direction in COMPETITIONS:
        lines.append(f"## {comp} ({metric}; {direction})")
        lines.append("")
        lines.append("| model | simple-baseline (240s) | good-baseline (600s) | sota-xgb (1200s) |")
        lines.append("|---|---:|---:|---:|")
        for model_id in model_ids:
            label = MODEL_LABELS.get(model_id, model_id)
            row = [label]
            ok = True
            for profile, budget in PROFILES:
                key = (comp, profile, budget, model_id)
                cell = series.get(key)
                if cell is None:
                    ok = False
                    row.append("n<5")
                else:
                    row.append(_fmt_stats(cell.values))
            lines.append("| " + " | ".join(row) + " |")
            if not ok:
                # Canonical set should have full 5-run coverage. Keep marker if data drifts.
                pass
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render v5.5 canonical10 stability supplement.")
    ap.add_argument("--check", action="store_true", help="Print output instead of writing file.")
    args = ap.parse_args()

    text = _render()
    if args.check:
        print(text, end="")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"updated: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
