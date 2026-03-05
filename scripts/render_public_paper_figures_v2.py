#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


REPO_ROOT = Path(__file__).resolve().parents[1]


def _short_model_label(model_id: str) -> str:
    model_id = str(model_id or "").strip()
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def _read_table(rel: str) -> pd.DataFrame:
    path = REPO_ROOT / rel
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _save(fig: plt.Figure, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _bbox_overlap_area(a, b) -> float:
    x0 = max(a.x0, b.x0)
    x1 = min(a.x1, b.x1)
    y0 = max(a.y0, b.y0)
    y1 = min(a.y1, b.y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((x1 - x0) * (y1 - y0))


def _place_non_overlapping_labels(
    ax,
    *,
    xs: pd.Series,
    ys: pd.Series,
    labels: pd.Series,
    fontsize: int = 8,
) -> None:
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer).expanded(0.98, 0.98)
    placed_bboxes = []
    directions = [
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
        (0, -1),
        (1, -1),
    ]
    rings = [12, 18, 24, 32, 40, 50, 62]
    offsets = [(dx * r, dy * r) for r in rings for (dx, dy) in directions]

    for x, y, label in zip(xs.tolist(), ys.tolist(), labels.tolist()):
        best_artist = None
        best_bbox = None
        best_score = None
        for dx, dy in offsets:
            artist = ax.annotate(
                str(label),
                xy=(float(x), float(y)),
                xytext=(dx, dy),
                textcoords="offset points",
                ha="left" if dx >= 0 else "right",
                va="center",
                fontsize=fontsize,
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#666666",
                    "lw": 0.7,
                    "shrinkA": 2.0,
                    "shrinkB": 2.0,
                },
                bbox={"boxstyle": "round,pad=0.14", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
            )
            fig.canvas.draw()
            bbox = artist.get_window_extent(renderer).expanded(1.03, 1.16)

            overlap = sum(_bbox_overlap_area(bbox, prev) for prev in placed_bboxes)
            outside = not axes_bbox.contains(bbox.x0, bbox.y0) or not axes_bbox.contains(bbox.x1, bbox.y1)
            dist = float((dx * dx + dy * dy) ** 0.5)
            score = overlap + (1e9 if outside else 0.0) + dist * 0.02

            if best_score is None or score < best_score:
                if best_artist is not None:
                    best_artist.remove()
                best_artist = artist
                best_bbox = bbox
                best_score = score
                if overlap == 0.0 and not outside and dist <= 18:
                    break
            else:
                artist.remove()

        if best_bbox is not None:
            placed_bboxes.append(best_bbox)


def _plot_leaderboard(scores: pd.DataFrame, *, variant: str, out_path: Path) -> None:
    df = scores[scores["variant"] == variant].copy()
    if df.empty:
        raise ValueError(f"No rows for variant={variant!r}")
    df["model_label"] = df["model_id"].map(_short_model_label)
    df = df.sort_values("score", ascending=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(df) + 1.0)))
    sns.barplot(data=df, x="score", y="model_label", color="#4C72B0", ax=ax)
    ax.set_xlabel("Performance score (0–1; higher is better)")
    ax.set_ylabel("")
    ax.set_xlim(0.0, 1.0)
    _save(fig, out_path)


def _plot_consistency_heatmap(consistency: pd.DataFrame, *, out_path: Path) -> None:
    df = consistency.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    pivot = df.pivot(index="model_label", columns="competition_id", values="rank")

    sns.set_theme(style="white")
    fig, ax = plt.subplots(figsize=(10, max(4.5, 0.45 * len(pivot) + 1.0)))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        cmap="viridis_r",
        cbar_kws={"label": "Rank (1=best)"},
        linewidths=0.5,
        linecolor="#dddddd",
        ax=ax,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    _save(fig, out_path)


def _plot_rank_stddev(stddev: pd.DataFrame, *, out_path: Path) -> None:
    df = stddev.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values("rank_stddev", ascending=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(df) + 1.0)))
    sns.barplot(data=df, x="rank_stddev", y="model_label", color="#55A868", ax=ax)
    ax.set_xlabel("Rank standard deviation (lower is more consistent)")
    ax.set_ylabel("")
    _save(fig, out_path)


def _plot_pareto(pareto: pd.DataFrame, *, out_path: Path) -> None:
    df = pareto.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values("performance_score", ascending=False).reset_index(drop=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    sc = ax.scatter(
        df["stability_rel_iqr"],
        df["performance_score"],
        c=df["success_rate"],
        cmap="viridis",
        s=90,
        edgecolors="black",
        linewidths=0.5,
    )
    _place_non_overlapping_labels(
        ax,
        xs=df["stability_rel_iqr"],
        ys=df["performance_score"],
        labels=df["model_label"],
        fontsize=8,
    )

    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Success rate")
    ax.set_xlabel("Stability (relative IQR; lower is better)")
    ax.set_ylabel("Performance score (0–1; higher is better)")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.02)
    _save(fig, out_path)


def _plot_success_rate(success: pd.DataFrame, *, out_path: Path) -> None:
    df = success.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values("success_rate", ascending=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(df) + 1.0)))
    sns.barplot(data=df, x="success_rate", y="model_label", color="#C44E52", ax=ax)
    ax.set_xlabel("Run success rate (higher is better)")
    ax.set_ylabel("")
    ax.set_xlim(0.0, 1.0)
    _save(fig, out_path)


def _plot_rel_iqr(stability: pd.DataFrame, *, out_path: Path) -> None:
    df = stability.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values("stability_rel_iqr", ascending=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(df) + 1.0)))
    sns.barplot(data=df, x="stability_rel_iqr", y="model_label", color="#8172B2", ax=ax)
    ax.set_xlabel("Stability (relative IQR; lower is better)")
    ax.set_ylabel("")
    ax.set_xlim(left=0)
    _save(fig, out_path)


def _plot_scaling_lines(points_by_budget: pd.DataFrame, *, out_path: Path) -> None:
    df = points_by_budget.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values(["budget"])

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=df,
        x="budget",
        y="avg_points",
        hue="model_label",
        marker="o",
        linewidth=2,
        ax=ax,
    )
    ax.set_xlabel("Time budget (seconds)")
    ax.set_ylabel("Average score across competitions (0–1)")
    ax.set_xticks(sorted(df["budget"].unique()))
    ax.set_ylim(0, 1.0)
    ax.legend(title="", bbox_to_anchor=(1.02, 1.0), loc="upper left", borderaxespad=0)
    _save(fig, out_path)


def _plot_marginal_gains(gains: pd.DataFrame, *, out_path: Path) -> None:
    df = gains.copy()
    df = df.rename(columns={"gain_240_to_600": "240→600", "gain_600_to_1200": "600→1200"})
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    melted = df.melt(id_vars=["model_label"], value_vars=["240→600", "600→1200"], var_name="interval", value_name="gain")
    order = df.sort_values("model_label")["model_label"].tolist()

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(12, 5.5))
    sns.barplot(data=melted, x="model_label", y="gain", hue="interval", order=order, ax=ax)
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_xlabel("")
    ax.set_ylabel("Change in average score (higher is better)")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.legend(title="Budget interval", loc="upper right")
    _save(fig, out_path)


def _plot_monotonicity(mono: pd.DataFrame, *, out_path: Path) -> None:
    df = mono.copy()
    df["model_label"] = df["model_label"].fillna(df["model_id"].map(_short_model_label))
    df = df.sort_values("monotone_rate", ascending=True)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(df) + 1.0)))
    sns.barplot(data=df, x="monotone_rate", y="model_label", color="#64B5CD", ax=ax)
    ax.set_xlabel("Monotonicity rate across competitions (higher is better)")
    ax.set_ylabel("")
    ax.set_xlim(0.0, 1.0)
    _save(fig, out_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--tables-dir",
        default="docs/paper/paper_assets_v3/tables",
        help="Directory containing the frozen v3 CSV tables.",
    )
    ap.add_argument(
        "--out-dir",
        default="docs/paper/figures_public_v2",
        help="Output directory for public-facing figures.",
    )
    args = ap.parse_args()

    tables_dir = str(args.tables_dir).rstrip("/")
    out_dir = REPO_ROOT / str(args.out_dir)

    leaderboard_scores = _read_table(f"{tables_dir}/leaderboard_scores.csv")
    _plot_leaderboard(
        leaderboard_scores,
        variant="best_budget_per_comp",
        out_path=out_dir / "leaderboard_primary_best_budget.png",
    )
    _plot_leaderboard(
        leaderboard_scores,
        variant="overall_all_cells",
        out_path=out_dir / "leaderboard_all_cells.png",
    )
    _plot_leaderboard(
        leaderboard_scores,
        variant="sota_only",
        out_path=out_dir / "leaderboard_1200s_only.png",
    )

    _plot_consistency_heatmap(
        _read_table(f"{tables_dir}/consistency_ranks_by_competition.csv"),
        out_path=out_dir / "consistency_ranks_heatmap.png",
    )
    _plot_rank_stddev(
        _read_table(f"{tables_dir}/consistency_rank_stddev.csv"),
        out_path=out_dir / "consistency_rank_stddev.png",
    )

    _plot_pareto(
        _read_table(f"{tables_dir}/reliability_pareto_table.csv"),
        out_path=out_dir / "reliability_pareto_performance_vs_stability.png",
    )
    _plot_success_rate(
        _read_table(f"{tables_dir}/reliability_success_rates.csv"),
        out_path=out_dir / "reliability_success_rate.png",
    )
    _plot_rel_iqr(
        _read_table(f"{tables_dir}/reliability_stability_rel_iqr.csv"),
        out_path=out_dir / "stability_relative_iqr.png",
    )

    _plot_scaling_lines(
        _read_table(f"{tables_dir}/scaling_points_by_budget.csv"),
        out_path=out_dir / "scaling_points_lines.png",
    )
    _plot_marginal_gains(
        _read_table(f"{tables_dir}/scaling_marginal_gains.csv"),
        out_path=out_dir / "scaling_marginal_gains.png",
    )
    _plot_monotonicity(
        _read_table(f"{tables_dir}/scaling_monotonicity.csv"),
        out_path=out_dir / "scaling_monotonicity_rate.png",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
