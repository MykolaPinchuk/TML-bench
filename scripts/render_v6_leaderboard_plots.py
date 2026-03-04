#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from check_profiled1_canonical_coverage import CANONICAL_MODELS
from update_profiled1_fiverun_tables import COMPETITIONS, PROFILES, SOURCE_DBS


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RunRow:
    run_id: str
    created_at: datetime
    competition_id: str
    prompt_profile: str
    budget_time_seconds: int
    provider: str
    model_id: str
    score_raw: float


def _parse_iso(ts: str | None) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    text = str(ts).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(r[1]) for r in cur.fetchall()}


def _iter_success_profiled1_runs(db_path: Path) -> list[RunRow]:
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
            out: list[RunRow] = []
            for run_id, created_at, comp, profile, budget, provider, model_id, score_raw, prompt_strategy in cur.fetchall():
                if prompt_strategy not in ("profiled1", None, ""):
                    continue
                if score_raw is None:
                    continue
                out.append(
                    RunRow(
                        run_id=str(run_id or "").strip(),
                        created_at=_parse_iso(created_at),
                        competition_id=str(comp or "").strip(),
                        prompt_profile=str(profile or "").strip(),
                        budget_time_seconds=int(budget or 0),
                        provider=str(provider or "").strip(),
                        model_id=str(model_id or "").strip(),
                        score_raw=float(score_raw),
                    )
                )
            return out

        cur.execute(
            """
            SELECT run_id, created_at, competition_id, prompt_profile, budget_time_seconds,
                   provider, model_id, score_raw
            FROM runs
            WHERE status='success'
            """
        )
        out = []
        for run_id, created_at, comp, profile, budget, provider, model_id, score_raw in cur.fetchall():
            if score_raw is None:
                continue
            out.append(
                RunRow(
                    run_id=str(run_id or "").strip(),
                    created_at=_parse_iso(created_at),
                    competition_id=str(comp or "").strip(),
                    prompt_profile=str(profile or "").strip(),
                    budget_time_seconds=int(budget or 0),
                    provider=str(provider or "").strip(),
                    model_id=str(model_id or "").strip(),
                    score_raw=float(score_raw),
                )
            )
        return out
    finally:
        con.close()


def _competition_direction() -> dict[str, int]:
    # +1 means higher is better; -1 means lower is better.
    out: dict[str, int] = {}
    for comp_id, _, direction in COMPETITIONS:
        if "higher" in direction:
            out[comp_id] = +1
        elif "lower" in direction:
            out[comp_id] = -1
        else:
            raise RuntimeError(f"Unknown direction for {comp_id}: {direction}")
    return out


def _load_canonical_medians() -> pd.DataFrame:
    comp_ids = {c for c, _, _ in COMPETITIONS}
    profile_budgets = {(p, b) for p, b in PROFILES}
    canonical_set = {(provider, model_id) for provider, model_id in CANONICAL_MODELS}

    seen_global: set[tuple[str, str]] = set()
    rows: list[RunRow] = []
    sources: list[Path] = []
    for rel in SOURCE_DBS:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        sources.append(src)
        for r in _iter_success_profiled1_runs(src):
            if r.competition_id not in comp_ids:
                continue
            if (r.prompt_profile, r.budget_time_seconds) not in profile_budgets:
                continue
            if (r.provider, r.model_id) not in canonical_set:
                continue
            if r.run_id:
                dedupe_key = ("run_id", r.run_id)
            else:
                dedupe_key = (
                    "fp",
                    (
                        f"{src.name}:{r.created_at.isoformat()}:{r.competition_id}:{r.prompt_profile}:"
                        f"{r.budget_time_seconds}:{r.provider}:{r.model_id}:{r.score_raw:.12g}"
                    ),
                )
            if dedupe_key in seen_global:
                continue
            seen_global.add(dedupe_key)
            rows.append(r)

    by_cell: dict[tuple[str, str, int, str, str], list[RunRow]] = {}
    for r in rows:
        key = (r.competition_id, r.prompt_profile, r.budget_time_seconds, r.provider, r.model_id)
        by_cell.setdefault(key, []).append(r)

    out_rows: list[dict[str, object]] = []
    for provider, model_id in CANONICAL_MODELS:
        for comp_id, _, _ in COMPETITIONS:
            for profile, budget in PROFILES:
                key = (comp_id, profile, budget, provider, model_id)
                cell = sorted(by_cell.get(key, []), key=lambda rr: (rr.created_at, rr.run_id))[:5]
                if len(cell) < 5:
                    raise RuntimeError(f"Underfilled cell for canonical model {provider}/{model_id}: {comp_id} {profile} {budget}")
                out_rows.append(
                    {
                        "competition_id": comp_id,
                        "profile": profile,
                        "budget": int(budget),
                        "provider": provider,
                        "model_id": model_id,
                        "median_score_raw": float(median([rr.score_raw for rr in cell])),
                    }
                )

    df = pd.DataFrame(out_rows)
    df["cell_id"] = df["competition_id"] + "|" + df["profile"] + "|" + df["budget"].astype(str)
    return df


def _rank_points(df: pd.DataFrame) -> pd.DataFrame:
    raise RuntimeError("_rank_points() is deprecated; use _minmax_points().")


def _minmax_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize within each (competition, budget) cell using absolute metric gaps.

    Steps:
    1) Convert metrics to a common 'higher is better' direction:
       value_hib = median_score_raw * direction, where direction is +1 or -1.
    2) Min-max normalize within the cell:
       points = (value_hib - min(value_hib)) / (max(value_hib) - min(value_hib)).

    This preserves absolute gaps linearly (within each cell), unlike rank-based points.
    """
    direction = _competition_direction()
    out = df.copy()
    out["direction"] = out["competition_id"].map(direction).astype(int)
    out["value_hib"] = out["median_score_raw"] * out["direction"]

    cell_min = out.groupby("cell_id")["value_hib"].transform("min")
    cell_max = out.groupby("cell_id")["value_hib"].transform("max")
    denom = (cell_max - cell_min).astype(float)

    out["points"] = (out["value_hib"] - cell_min) / denom.replace(0.0, pd.NA)
    out["points"] = out["points"].fillna(0.5).astype(float)
    return out


def _agg_overall(points_df: pd.DataFrame) -> pd.DataFrame:
    # Equal weight across competitions; equal weight across budgets within each competition.
    # Equivalent to equal weight per-cell since every competition has 3 budgets.
    g = points_df.groupby(["model_id"], as_index=False)["points"].mean()
    g = g.rename(columns={"points": "score"})
    g["variant"] = "overall_all_cells"
    return g


def _agg_sota_only(points_df: pd.DataFrame) -> pd.DataFrame:
    g = points_df[points_df["profile"] == "sota-xgb"].groupby(["model_id"], as_index=False)["points"].mean()
    g = g.rename(columns={"points": "score"})
    g["variant"] = "sota_only"
    return g


def _agg_best_budget_per_comp(points_df: pd.DataFrame) -> pd.DataFrame:
    # For each (model, competition), take best points across budgets, then average competitions equally.
    tmp = (
        points_df.groupby(["model_id", "competition_id"], as_index=False)["points"]
        .max()
        .rename(columns={"points": "best_points"})
    )
    g = tmp.groupby(["model_id"], as_index=False)["best_points"].mean().rename(columns={"best_points": "score"})
    g["variant"] = "best_budget_per_comp"
    return g


def _short_model_name(model_id: str) -> str:
    # Keep human-readable but stable.
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def _plot_bar(df_scores: pd.DataFrame, out_path: Path, title: str) -> None:
    dfp = df_scores.copy()
    dfp["label"] = dfp["model_id"].map(_short_model_name)
    dfp = dfp.sort_values("score", ascending=True)  # horizontal, top is best at end

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(11, max(4.5, 0.45 * len(dfp) + 1.0)))
    ax = sns.barplot(data=dfp, y="label", x="score", color="#2C7FB8")
    ax.set_title(title)
    ax.set_xlabel("Aggregate score (min-max normalized within each setting; 0=worst, 1=best)")
    ax.set_ylabel("")
    ax.set_xlim(0.0, 1.0)

    for i, (_, row) in enumerate(dfp.iterrows()):
        v = float(row["score"])
        ax.text(min(0.995, v + 0.01), i, f"{v:.3f}", va="center", ha="left", fontsize=9)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Render v6 candidate leaderboard plots (canonical 10 models).")
    ap.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "tmp" / "v6_plots"),
        help="Output directory for plots (default: tmp/v6_plots).",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    med = _load_canonical_medians()
    pts = _minmax_points(med)

    scores = pd.concat([_agg_overall(pts), _agg_sota_only(pts), _agg_best_budget_per_comp(pts)], ignore_index=True)

    for variant, title in [
        ("overall_all_cells", "Aggregate performance leaderboard (all competitions, all budgets)"),
        ("sota_only", "Aggregate performance leaderboard (1200s only)"),
        ("best_budget_per_comp", "Aggregate performance leaderboard (best budget per competition)"),
    ]:
        dfv = scores[scores["variant"] == variant][["model_id", "score"]].copy()
        _plot_bar(dfv, out_dir / f"leaderboard_{variant}.png", title)

    # Also emit the raw scores as CSV for quick inspection.
    csv_path = out_dir / "leaderboard_scores.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(csv_path, index=False)

    print(f"wrote_dir={out_dir}")
    print(f"wrote_csv={csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
