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
import numpy as np
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
    status: str
    score_raw: float | None


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


def _tokenish_columns(cols: set[str]) -> list[str]:
    out: list[str] = []
    for c in sorted(cols):
        low = c.lower()
        if any(k in low for k in ["token", "cost", "usd", "price", "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens"]):
            out.append(c)
    return out


def _iter_runs(db_path: Path) -> list[RunRow]:
    con = sqlite3.connect(db_path)
    try:
        cols = _table_columns(con, "runs")
        has_prompt_strategy = "prompt_strategy" in cols
        cur = con.cursor()

        if has_prompt_strategy:
            cur.execute(
                """
                SELECT run_id, created_at, competition_id, prompt_profile, budget_time_seconds,
                       provider, model_id, status, score_raw, prompt_strategy
                FROM runs
                """
            )
            out: list[RunRow] = []
            for run_id, created_at, comp, profile, budget, provider, model_id, status, score_raw, prompt_strategy in cur.fetchall():
                if prompt_strategy not in ("profiled1", None, ""):
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
                        status=str(status or "").strip(),
                        score_raw=float(score_raw) if score_raw is not None else None,
                    )
                )
            return out

        cur.execute(
            """
            SELECT run_id, created_at, competition_id, prompt_profile, budget_time_seconds,
                   provider, model_id, status, score_raw
            FROM runs
            """
        )
        out = []
        for run_id, created_at, comp, profile, budget, provider, model_id, status, score_raw in cur.fetchall():
            out.append(
                RunRow(
                    run_id=str(run_id or "").strip(),
                    created_at=_parse_iso(created_at),
                    competition_id=str(comp or "").strip(),
                    prompt_profile=str(profile or "").strip(),
                    budget_time_seconds=int(budget or 0),
                    provider=str(provider or "").strip(),
                    model_id=str(model_id or "").strip(),
                    status=str(status or "").strip(),
                    score_raw=float(score_raw) if score_raw is not None else None,
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


def _dedupe_key(src_name: str, r: RunRow) -> tuple[str, str]:
    if r.run_id:
        return ("run_id", r.run_id)
    return (
        "fp",
        (
            f"{src_name}:{r.created_at.isoformat()}:{r.competition_id}:{r.prompt_profile}:{r.budget_time_seconds}:"
            f"{r.provider}:{r.model_id}:{r.status}:{'' if r.score_raw is None else f'{r.score_raw:.12g}'}"
        ),
    )


def _load_filtered_runs() -> pd.DataFrame:
    comp_ids = {c for c, _, _ in COMPETITIONS}
    profile_budgets = {(p, b) for p, b in PROFILES}
    canonical_set = {(provider, model_id) for provider, model_id in CANONICAL_MODELS}

    seen_global: set[tuple[str, str]] = set()
    out_rows: list[dict[str, object]] = []
    for rel in SOURCE_DBS:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        for r in _iter_runs(src):
            if r.competition_id not in comp_ids:
                continue
            if (r.prompt_profile, r.budget_time_seconds) not in profile_budgets:
                continue
            if (r.provider, r.model_id) not in canonical_set:
                continue
            dk = _dedupe_key(src.name, r)
            if dk in seen_global:
                continue
            seen_global.add(dk)
            out_rows.append(
                {
                    "created_at": r.created_at,
                    "competition_id": r.competition_id,
                    "profile": r.prompt_profile,
                    "budget": int(r.budget_time_seconds),
                    "provider": r.provider,
                    "model_id": r.model_id,
                    "status": r.status,
                    "score_raw": r.score_raw,
                }
            )

    df = pd.DataFrame(out_rows)
    df["cell_id"] = df["competition_id"] + "|" + df["profile"] + "|" + df["budget"].astype(str)
    return df


def _canonical_medians_from_runs(df_runs: pd.DataFrame) -> pd.DataFrame:
    # Use earliest 5 successful runs per (competition, profile, budget, model).
    df = df_runs[df_runs["status"] == "success"].copy()
    if df.empty:
        raise RuntimeError("No successful runs found for canonical set.")

    df = df.sort_values(["created_at"], ascending=True)
    grouped = (
        df.groupby(["competition_id", "profile", "budget", "model_id"], as_index=False)
        .head(5)
        .groupby(["competition_id", "profile", "budget", "model_id"], as_index=False)["score_raw"]
        .agg(["count", "median"])
        .reset_index()
        .rename(columns={"median": "median_score_raw"})
    )
    if (grouped["count"] < 5).any():
        bad = grouped[grouped["count"] < 5].head(5)
        raise RuntimeError(f"Underfilled canonical medians; example rows:\n{bad}")

    grouped["cell_id"] = grouped["competition_id"] + "|" + grouped["profile"] + "|" + grouped["budget"].astype(str)
    return grouped[["competition_id", "profile", "budget", "model_id", "median_score_raw", "cell_id"]]


def _rank_points(medians: pd.DataFrame) -> pd.DataFrame:
    direction = _competition_direction()
    out = medians.copy()
    out["direction"] = out["competition_id"].map(direction).astype(int)
    out["value_for_rank"] = out["median_score_raw"] * out["direction"]
    out["n_models"] = out.groupby("cell_id")["model_id"].transform("count").astype(int)
    out["rank"] = out.groupby("cell_id")["value_for_rank"].rank(method="first", ascending=False)
    out["points"] = (out["n_models"] - out["rank"]) / (out["n_models"] - 1)
    return out


def _short_model_name(model_id: str) -> str:
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def _write_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def _plot_rank_heatmap(df: pd.DataFrame, out_path: Path, title: str) -> None:
    # df columns: model_label, competition_id, rank (1=best)
    pivot = df.pivot(index="model_label", columns="competition_id", values="rank")
    sns.set_theme(style="white")
    plt.figure(figsize=(10, max(4.5, 0.45 * len(pivot) + 1.0)))
    ax = sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        cmap="viridis_r",
        cbar_kws={"label": "Rank (1=best)"},
        linewidths=0.5,
        linecolor="#dddddd",
    )
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _plot_bar(df: pd.DataFrame, out_path: Path, title: str, x_col: str, x_label: str) -> None:
    sns.set_theme(style="whitegrid")
    dfp = df.copy().sort_values(x_col, ascending=True)
    plt.figure(figsize=(11, max(4.5, 0.45 * len(dfp) + 1.0)))
    ax = sns.barplot(data=dfp, y="model_label", x=x_col, color="#2C7FB8")
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel("")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _plot_scatter(df: pd.DataFrame, out_path: Path, title: str) -> None:
    # Expect columns: performance_score, stability_rel_iqr, success_rate
    sns.set_theme(style="whitegrid")
    dfp = df.copy()
    plt.figure(figsize=(10.5, 6.5))
    ax = plt.gca()
    sc = ax.scatter(
        dfp["performance_score"],
        dfp["stability_rel_iqr"],
        c=dfp["success_rate"],
        s=80,
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        edgecolors="black",
        linewidths=0.5,
        alpha=0.9,
    )
    for _, r in dfp.iterrows():
        ax.text(
            float(r["performance_score"]) + 0.01,
            float(r["stability_rel_iqr"]),
            str(r["model_label"]),
            fontsize=8,
            va="center",
        )
    ax.set_title(title)
    ax.set_xlabel("Performance (headline normalized score; 0=worst, 1=best)")
    ax.set_ylabel("Stability (median relative IQR across cells; lower is better)")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(bottom=0.0)
    plt.colorbar(sc, ax=ax, label="Success rate (all attempts; profiled1)")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Render v6 Result 0.5/2/3 plots (canonical 10 models).")
    ap.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "docs" / "paper" / "figures" / "v6"),
        help="Output directory for committed figures (default: docs/paper/figures/v6).",
    )
    args = ap.parse_args()
    out_dir = Path(args.out_dir)

    # Token accounting is a key planned result; record what's actually present in the sqlite schema.
    token_rows: list[dict[str, object]] = []
    token_union: set[str] = set()
    for rel in SOURCE_DBS:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        con = sqlite3.connect(src)
        try:
            cols = _table_columns(con, "runs")
        finally:
            con.close()
        tok = _tokenish_columns(cols)
        token_rows.append({"db": str(src.relative_to(REPO_ROOT)), "tokenish_columns": ",".join(tok)})
        token_union.update(tok)

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(token_rows).to_csv(out_dir / "token_columns_by_db.csv", index=False)
    (out_dir / "token_columns_union.txt").write_text("\n".join(sorted(token_union)) + ("\n" if token_union else ""), encoding="utf-8")

    df_runs = _load_filtered_runs()
    med = _canonical_medians_from_runs(df_runs)
    pts = _rank_points(med)

    # Headline performance score (best budget per competition; avg over competitions).
    perf = (
        pts.groupby(["model_id", "competition_id"], as_index=False)["points"]
        .max()
        .groupby("model_id", as_index=False)["points"]
        .mean()
        .rename(columns={"points": "performance_score"})
    )
    perf["model_label"] = perf["model_id"].map(_short_model_name)

    # Result 0.5: consistency across competitions (use same best-budget-per-comp points as headline, per competition).
    by_comp = pts.groupby(["model_id", "competition_id"], as_index=False)["points"].max()
    by_comp["rank"] = by_comp.groupby("competition_id")["points"].rank(method="first", ascending=False)
    by_comp["model_label"] = by_comp["model_id"].map(_short_model_name)
    _write_csv(by_comp.sort_values(["competition_id", "rank"]), out_dir / "consistency_ranks_by_competition.csv")
    _plot_rank_heatmap(
        by_comp[["model_label", "competition_id", "rank"]],
        out_dir / "result0_5_consistency_ranks_heatmap.png",
        "Result 0.5: Per-competition ranks (best budget per competition; 1=best)",
    )

    rank_std = (
        by_comp.groupby("model_id", as_index=False)["rank"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"std": "rank_stddev", "mean": "rank_mean"})
    )
    rank_std["model_label"] = rank_std["model_id"].map(_short_model_name)
    _write_csv(rank_std.sort_values("rank_stddev", ascending=False), out_dir / "consistency_rank_stddev.csv")
    _plot_bar(
        rank_std[["model_label", "rank_stddev"]],
        out_dir / "result0_5_consistency_rank_stddev.png",
        "Result 0.5: Rank variability across competitions (stddev; lower is more consistent)",
        "rank_stddev",
        "Rank stddev across 4 competitions",
    )

    # Result 2a: success rate (all attempts; profiled1) for canonical suite cells.
    attempts = (
        df_runs.groupby(["model_id", "status"], as_index=False)
        .size()
        .rename(columns={"size": "n"})
        .pivot(index="model_id", columns="status", values="n")
        .fillna(0)
        .reset_index()
    )
    attempts["attempts_total"] = attempts.drop(columns=["model_id"]).sum(axis=1)
    attempts["successes"] = attempts.get("success", 0)
    attempts["success_rate"] = attempts["successes"] / attempts["attempts_total"].replace(0, np.nan)
    attempts["model_label"] = attempts["model_id"].map(_short_model_name)
    _write_csv(attempts.sort_values("success_rate", ascending=False), out_dir / "reliability_success_rates.csv")
    _plot_bar(
        attempts[["model_label", "success_rate"]],
        out_dir / "result2_reliability_success_rate.png",
        "Result 2: Success rate across all attempts (profiled1; canonical suite cells)",
        "success_rate",
        "Success rate (success / total attempts)",
    )

    # Result 2b: stability via IQR/|median| across canonical 5-run cells.
    first5 = (
        df_runs[df_runs["status"] == "success"]
        .sort_values(["created_at"], ascending=True)
        .groupby(["competition_id", "profile", "budget", "model_id"], as_index=False)
        .head(5)
    )
    def _iqr(x: pd.Series) -> float:
        q1 = float(np.quantile(x, 0.25))
        q3 = float(np.quantile(x, 0.75))
        return q3 - q1

    cell_stats = (
        first5.groupby(["competition_id", "profile", "budget", "model_id"], as_index=False)["score_raw"]
        .agg(iqr=_iqr, median="median", count="count")
    )
    if (cell_stats["count"] < 5).any():
        bad = cell_stats[cell_stats["count"] < 5].head(5)
        raise RuntimeError(f"Underfilled stability cells; example rows:\n{bad}")

    eps = 1e-12
    cell_stats["rel_iqr"] = cell_stats["iqr"] / (cell_stats["median"].abs() + eps)
    stability = (
        cell_stats.groupby("model_id", as_index=False)["rel_iqr"]
        .median()
        .rename(columns={"rel_iqr": "stability_rel_iqr"})
    )
    stability["model_label"] = stability["model_id"].map(_short_model_name)
    _write_csv(stability.sort_values("stability_rel_iqr", ascending=True), out_dir / "reliability_stability_rel_iqr.csv")
    _plot_bar(
        stability[["model_label", "stability_rel_iqr"]],
        out_dir / "result2_stability_rel_iqr.png",
        "Result 2: Stability (median relative IQR across canonical 5-run cells; lower is better)",
        "stability_rel_iqr",
        "Median(IQR/|median|) across 12 cells",
    )

    # Pareto plot: performance vs stability, colored by success rate.
    merged = perf.merge(stability[["model_id", "stability_rel_iqr"]], on="model_id", how="left").merge(
        attempts[["model_id", "success_rate", "attempts_total"]], on="model_id", how="left"
    )
    merged["model_label"] = merged["model_id"].map(_short_model_name)
    _write_csv(merged.sort_values("performance_score", ascending=False), out_dir / "reliability_pareto_table.csv")
    _plot_scatter(
        merged[["performance_score", "stability_rel_iqr", "success_rate", "model_label"]],
        out_dir / "result2_pareto_performance_vs_stability.png",
        "Result 2: Performance vs stability (color=success rate)",
    )

    # Result 3: scaling across budgets in normalized points space.
    by_budget = (
        pts.groupby(["model_id", "profile", "budget"], as_index=False)["points"]
        .mean()
        .rename(columns={"points": "avg_points"})
    )
    by_budget["model_label"] = by_budget["model_id"].map(_short_model_name)
    _write_csv(by_budget.sort_values(["model_id", "budget"]), out_dir / "scaling_points_by_budget.csv")

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 6.5))
    ax = sns.lineplot(data=by_budget, x="budget", y="avg_points", hue="model_label", marker="o")
    ax.set_title("Result 3: Performance scaling with time budget (avg normalized points across competitions)")
    ax.set_xlabel("Budget seconds")
    ax.set_ylabel("Avg normalized points (0..1)")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.0, title="")
    plt.tight_layout()
    plt.savefig(out_dir / "result3_scaling_points_lines.png", dpi=200)
    plt.close()

    # Marginal gains.
    wide = by_budget.pivot(index="model_id", columns="budget", values="avg_points").reset_index()
    wide["gain_240_to_600"] = wide[600] - wide[240]
    wide["gain_600_to_1200"] = wide[1200] - wide[600]
    wide["model_label"] = wide["model_id"].map(_short_model_name)
    gains = wide[["model_id", "model_label", "gain_240_to_600", "gain_600_to_1200"]].copy()
    _write_csv(gains.sort_values("gain_240_to_600", ascending=False), out_dir / "scaling_marginal_gains.csv")

    gains_long = gains.melt(id_vars=["model_label"], value_vars=["gain_240_to_600", "gain_600_to_1200"], var_name="gain", value_name="delta")
    gains_long["gain"] = gains_long["gain"].map({"gain_240_to_600": "240→600", "gain_600_to_1200": "600→1200"})
    plt.figure(figsize=(11, max(4.5, 0.45 * len(gains) + 1.0)))
    ax = sns.barplot(data=gains_long, y="model_label", x="delta", hue="gain")
    ax.set_title("Result 3: Marginal gains vs extra time (normalized points)")
    ax.set_xlabel("Delta avg points")
    ax.set_ylabel("")
    ax.legend(title="")
    plt.tight_layout()
    plt.savefig(out_dir / "result3_scaling_marginal_gains.png", dpi=200)
    plt.close()

    # Monotonicity in raw medians (direction-correct).
    direction = _competition_direction()
    m = med.copy()
    m["dir"] = m["competition_id"].map(direction).astype(int)
    m["value_hib"] = m["median_score_raw"] * m["dir"]
    mw = m.pivot(index=["model_id", "competition_id"], columns="budget", values="value_hib").reset_index()
    mw["is_monotone"] = (mw[240] <= mw[600]) & (mw[600] <= mw[1200])
    mono = mw.groupby("model_id", as_index=False)["is_monotone"].mean().rename(columns={"is_monotone": "monotone_rate"})
    mono["model_label"] = mono["model_id"].map(_short_model_name)
    _write_csv(mono.sort_values("monotone_rate", ascending=False), out_dir / "scaling_monotonicity.csv")
    _plot_bar(
        mono[["model_label", "monotone_rate"]],
        out_dir / "result3_monotonicity_rate.png",
        "Result 3: Monotonicity across budgets (share of competitions monotone; higher is better)",
        "monotone_rate",
        "Monotonicity rate (0..1 across 4 competitions)",
    )

    print(f"wrote_dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
