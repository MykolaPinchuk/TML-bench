from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from orchestrator.db import ensure_db, fetch_baselines, fetch_runs, insert_run
from orchestrator.result import read_result_json


@dataclass(frozen=True)
class LeaderboardPaths:
    json_path: Path
    csv_path: Path
    html_path: Path


def load_baselines_df(*, db_path: Path) -> pd.DataFrame:
    try:
        rows = fetch_baselines(db_path)
    except Exception:  # noqa: BLE001
        rows = []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _is_runnable_model(*, provider: object, model_id: object) -> bool:
    p = str(provider or "").strip()
    m = str(model_id or "").strip()
    if not p or not m:
        return False
    if any(ch.isspace() for ch in m):
        return False
    if p == "nanogpt":
        return "/" in m
    if p == "chutes":
        return ("/" in m) or (m in {"deepseek-v3.1-terminus"})
    return True


def _pacific_tz_name() -> str:
    return "America/Los_Angeles"


def _get_pacific_tz():
    try:
        from zoneinfo import ZoneInfo  # type: ignore

        return ZoneInfo(_pacific_tz_name())
    except Exception:
        return None


def _parse_iso_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_created_at_pacific(s: str | None) -> str | None:
    dt = _parse_iso_datetime(s)
    if dt is None:
        return None if s is None else str(s)
    pacific_tz = _get_pacific_tz()
    if pacific_tz is None:
        # Fallback: keep in UTC if tz database isn't available.
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return dt.astimezone(pacific_tz).replace(microsecond=0).isoformat()


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    # Avoid dtype issues (e.g., nullable Int64 columns) when filling missing values.
    df = df.astype(object).where(df.notna(), "")
    cols = list(df.columns)
    if not cols:
        return "_(empty)_\n"

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = str(row[c])
            v = v.replace("\n", " ").replace("|", "\\|")
            vals.append(v)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def _score_normalized_series(df: pd.DataFrame) -> pd.Series:
    """
    Return a higher-is-better score series.

    Prefer the DB-provided `score_normalized` when available; otherwise derive from metric_name.
    """
    if "score_normalized" in df.columns:
        s = pd.to_numeric(df["score_normalized"], errors="coerce")
        if s.notna().any():
            return s

    if "score_raw" not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index, dtype="float64")

    raw = pd.to_numeric(df["score_raw"], errors="coerce")
    metric = df["metric_name"] if "metric_name" in df.columns else pd.Series([""] * len(df), index=df.index)
    metric = metric.astype(str).str.strip().str.lower()

    # Current supported metrics: rmse/mae/logloss (lower is better), auc (higher is better).
    higher_is_better = metric.isin(["auc"])
    out = raw.copy()
    out[~higher_is_better] = -raw[~higher_is_better]
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _core_suite_competitions() -> list[str]:
    """
    Return the canonical 4-competition suite, if present.
    Falls back to [] if the suite file can't be loaded.
    """
    p = _repo_root() / "orchestrator" / "suites" / "v5_core.json"
    if not p.exists():
        return []
    try:
        import json

        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    comps = raw.get("competitions")
    if not isinstance(comps, list):
        return []
    out: list[str] = []
    for c in comps:
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
    # Keep it "just 4" as requested.
    return out[:4]


def _competition_mean_score_columns(
    *,
    successes: pd.DataFrame,
    config_cols: list[str],
    competitions: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Returns a (df_wide, columns) pair where df_wide has one row per config (index=config_cols)
    and one column per competition containing mean score_raw over successful runs.
    """
    if successes.empty or not competitions:
        return pd.DataFrame(), []
    needed = {"competition_id", "score_raw"}
    if not needed.issubset(set(successes.columns)):
        return pd.DataFrame(), []

    d = successes.copy()
    d["competition_id"] = d["competition_id"].fillna("").astype(str)
    d = d[d["competition_id"].isin(set(competitions))]
    if d.empty:
        return pd.DataFrame(), []
    d["score_raw"] = pd.to_numeric(d["score_raw"], errors="coerce")
    d = d[pd.notna(d["score_raw"])]
    if d.empty:
        return pd.DataFrame(), []

    for c in config_cols:
        if c in d.columns:
            d[c] = d[c].fillna("").astype(str)

    comp_mean = (
        d.groupby(["competition_id"] + config_cols, dropna=False)
        .agg(mean_score_raw=("score_raw", "mean"))
        .reset_index()
    )
    wide = comp_mean.pivot_table(index=config_cols, columns="competition_id", values="mean_score_raw", aggfunc="mean")
    # Ensure stable column ordering and only the requested 4 competitions.
    cols = [c for c in competitions if c in wide.columns]
    if not cols:
        return pd.DataFrame(), []
    wide = wide[cols].reset_index()

    # Rename to concise, explicit column names.
    rename = {c: f"{c}_mean" for c in cols}
    wide = wide.rename(columns=rename)
    return wide, [rename[c] for c in cols]


def _overall_by_model_df(df: pd.DataFrame, *, baselines: pd.DataFrame | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    needed = {"competition_id", "provider", "model_id", "run_id"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()

    d = df.copy()
    d["_score_norm"] = _score_normalized_series(d)
    d["status"] = d["status"].fillna("").astype(str) if "status" in d.columns else ""

    config_cols = ["provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"]
    config_cols = [c for c in config_cols if c in d.columns]
    if not config_cols:
        return pd.DataFrame()

    for c in config_cols + ["competition_id"]:
        d[c] = d[c].fillna("").astype(str)

    attempts = d.groupby(config_cols, dropna=False).agg(
        runs=("run_id", "size"),
        run_success=("status", lambda s: int((s == "success").sum())),
        competitions_attempted=("competition_id", "nunique"),
    )
    attempts = attempts.reset_index()
    attempts["run_success_rate"] = attempts["run_success"] / attempts["runs"]

    # Time usage (fraction of budget used).
    if "runtime_seconds" in d.columns and "budget_time_seconds" in d.columns:
        d["_runtime_seconds"] = pd.to_numeric(d["runtime_seconds"], errors="coerce")
        d["_budget_seconds"] = pd.to_numeric(d["budget_time_seconds"], errors="coerce")
        mask = d["_runtime_seconds"].notna() & d["_budget_seconds"].notna() & (d["_budget_seconds"] > 0)
        d["_time_used_frac"] = pd.NA
        d.loc[mask, "_time_used_frac"] = d.loc[mask, "_runtime_seconds"] / d.loc[mask, "_budget_seconds"]
        time_agg = d.groupby(config_cols, dropna=False).agg(
            runtime_mean_seconds=("_runtime_seconds", "mean"),
            mean_time_used=("_time_used_frac", "mean"),
        )
        time_agg = time_agg.reset_index()
        attempts = attempts.merge(time_agg, on=config_cols, how="left")

    successes = d[d["status"] == "success"].copy()
    if successes.empty:
        return pd.DataFrame()

    comp_success = (
        successes.groupby(config_cols, dropna=False)
        .agg(competitions_succeeded=("competition_id", "nunique"))
        .reset_index()
    )
    out = attempts.merge(comp_success, on=config_cols, how="left")
    out["competitions_succeeded"] = out["competitions_succeeded"].fillna(0).astype(int)
    out["competition_success_rate"] = out["competitions_succeeded"] / out["competitions_attempted"].replace(0, pd.NA)

    best = (
        successes.groupby(["competition_id"] + config_cols, dropna=False)
        .agg(best_score_norm=("_score_norm", "max"))
        .reset_index()
    )
    if best.empty:
        return pd.DataFrame()

    best["_configs_in_comp"] = best.groupby("competition_id")["best_score_norm"].transform("size")
    best["rank"] = best.groupby("competition_id")["best_score_norm"].rank(ascending=False, method="min")
    best["rank_pct"] = 0.0
    mask = best["_configs_in_comp"] > 1
    best.loc[mask, "rank_pct"] = (best.loc[mask, "rank"] - 1.0) / (best.loc[mask, "_configs_in_comp"] - 1.0)

    ranks = best.groupby(config_cols, dropna=False).agg(
        competitions_ranked=("competition_id", "nunique"),
        mean_rank=("rank", "mean"),
        mean_rank_pct=("rank_pct", "mean"),
        best_rank=("rank", "min"),
    )
    ranks = ranks.reset_index()

    out = out.merge(ranks, on=config_cols, how="left")

    # Per-competition score columns (mean score_raw across successful runs).
    core_comps = _core_suite_competitions()
    comp_wide, comp_cols = _competition_mean_score_columns(
        successes=successes,
        config_cols=config_cols,
        competitions=core_comps,
    )
    if not comp_wide.empty and comp_cols:
        out = out.merge(comp_wide, on=config_cols, how="left")

    if "competitions_ranked" in out.columns:
        out["competitions_ranked"] = pd.to_numeric(out["competitions_ranked"], errors="coerce").astype("Int64")

    # Baseline-normalized absolute signal (dimensionless):
    # abs_units = 0 -> constant baseline; abs_units = 1 -> hgb baseline.
    if baselines is not None and not baselines.empty and {"competition_id", "baseline_type", "score_normalized"}.issubset(set(baselines.columns)):
        b = baselines.copy()
        b["competition_id"] = b["competition_id"].fillna("").astype(str)
        b["baseline_type"] = b["baseline_type"].fillna("").astype(str)
        b["score_normalized"] = pd.to_numeric(b["score_normalized"], errors="coerce")
        pivot = (
            b.pivot_table(index="competition_id", columns="baseline_type", values="score_normalized", aggfunc="max")
            .reset_index()
            .rename(columns={"constant": "baseline_constant_norm", "hgb": "baseline_hgb_norm"})
        )
        best2 = best.merge(pivot, on="competition_id", how="left")
        if "baseline_constant_norm" in best2.columns and "baseline_hgb_norm" in best2.columns:
            den = best2["baseline_hgb_norm"] - best2["baseline_constant_norm"]
            best2["abs_units"] = (best2["best_score_norm"] - best2["baseline_constant_norm"]) / den.replace(0, pd.NA)
            # Only trust scaling when hgb is better than constant (den > 0).
            best2.loc[den <= 0, "abs_units"] = pd.NA
            best2["beat_hgb"] = (best2["best_score_norm"] > best2["baseline_hgb_norm"]).astype("Int64")

            abs_agg = best2.groupby(config_cols, dropna=False).agg(
                competitions_abs=("abs_units", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
                mean_abs_units=("abs_units", "mean"),
                median_abs_units=("abs_units", "median"),
                beat_hgb=("beat_hgb", "sum"),
            )
            abs_agg = abs_agg.reset_index()
            abs_agg["beat_hgb_rate"] = abs_agg["beat_hgb"] / abs_agg["competitions_abs"].replace(0, pd.NA)
            out = out.merge(abs_agg, on=config_cols, how="left")

    out["mean_rank"] = pd.to_numeric(out["mean_rank"], errors="coerce").round(2)
    out["best_rank"] = pd.to_numeric(out["best_rank"], errors="coerce").astype("Int64")
    out["mean_rank_pct"] = pd.to_numeric(out["mean_rank_pct"], errors="coerce").round(4)
    out["competition_success_rate"] = pd.to_numeric(out["competition_success_rate"], errors="coerce").round(4)
    out["run_success_rate"] = pd.to_numeric(out["run_success_rate"], errors="coerce").round(4)
    for c in comp_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(6)
    if "runtime_mean_seconds" in out.columns:
        out["runtime_mean_seconds"] = pd.to_numeric(out["runtime_mean_seconds"], errors="coerce").round(1)
    if "mean_time_used" in out.columns:
        out["mean_time_used"] = pd.to_numeric(out["mean_time_used"], errors="coerce").round(4)
    if "mean_abs_units" in out.columns:
        out["mean_abs_units"] = pd.to_numeric(out["mean_abs_units"], errors="coerce").round(3)
    if "median_abs_units" in out.columns:
        out["median_abs_units"] = pd.to_numeric(out["median_abs_units"], errors="coerce").round(3)
    if "beat_hgb_rate" in out.columns:
        out["beat_hgb_rate"] = pd.to_numeric(out["beat_hgb_rate"], errors="coerce").round(4)

    def _pct(x: object) -> str:
        try:
            v = float(x)
            if pd.isna(v):
                return ""
            return f"{100.0 * v:.1f}%"
        except Exception:  # noqa: BLE001
            return ""

    out["competition_success_rate"] = out["competition_success_rate"].map(_pct)
    out["run_success_rate"] = out["run_success_rate"].map(_pct)
    out["mean_rank_pct"] = out["mean_rank_pct"].map(_pct)
    if "mean_time_used" in out.columns:
        out["mean_time_used"] = out["mean_time_used"].map(_pct)
    if "beat_hgb_rate" in out.columns:
        out["beat_hgb_rate"] = out["beat_hgb_rate"].map(_pct)

    cols = config_cols + [
        "competitions_attempted",
        "competitions_succeeded",
        "competition_success_rate",
        "runs",
        "run_success_rate",
        "runtime_mean_seconds",
        "mean_time_used",
        "competitions_ranked",
        # Requested: per-competition mean scores go right after competitions_ranked.
        *comp_cols,
        "mean_rank",
        "mean_rank_pct",
        "best_rank",
        "competitions_abs",
        "mean_abs_units",
        "median_abs_units",
        "beat_hgb_rate",
    ]
    cols = [c for c in cols if c in out.columns]
    out = out[cols]

    # mean_rank_pct is a percent string; sort using numeric extraction.
    out["_sort_rank_pct"] = pd.to_numeric(
        out["mean_rank_pct"].astype(str).str.replace("%", "", regex=False),
        errors="coerce",
    )
    out = out.sort_values(by=["_sort_rank_pct", "competitions_succeeded"], ascending=[True, False], na_position="last")
    out = out.drop(columns=["_sort_rank_pct"])

    return out


def _overall_by_model_robust_df(df: pd.DataFrame, *, baselines: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    More robust overall view:
    - Per competition/config uses the MEDIAN normalized score across successful runs (not best-of).
    - Computes per-competition percentile ranks from those medians.
    - Reports uncertainty across competitions via rank_pct p25/p50/p75.
    - Also reports an "expected" rank_pct that treats competitions with no success as worst (100%).
    """
    if df.empty:
        return pd.DataFrame()
    needed = {"competition_id", "provider", "model_id", "run_id"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()

    d = df.copy()
    d["_score_norm"] = _score_normalized_series(d)
    d["status"] = d["status"].fillna("").astype(str) if "status" in d.columns else ""

    config_cols = ["provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"]
    config_cols = [c for c in config_cols if c in d.columns]
    if not config_cols:
        return pd.DataFrame()

    for c in config_cols + ["competition_id"]:
        d[c] = d[c].fillna("").astype(str)

    # Attempt counts (all statuses).
    attempts = d.groupby(["competition_id"] + config_cols, dropna=False).agg(
        runs=("run_id", "size"),
        run_success=("status", lambda s: int((s == "success").sum())),
    )
    attempts = attempts.reset_index()
    attempts["run_success_rate"] = attempts["run_success"] / attempts["runs"]

    # Time usage (fraction of budget used), averaged per (competition_id, config).
    if "runtime_seconds" in d.columns and "budget_time_seconds" in d.columns:
        d["_runtime_seconds"] = pd.to_numeric(d["runtime_seconds"], errors="coerce")
        d["_budget_seconds"] = pd.to_numeric(d["budget_time_seconds"], errors="coerce")
        mask = d["_runtime_seconds"].notna() & d["_budget_seconds"].notna() & (d["_budget_seconds"] > 0)
        d["_time_used"] = pd.NA
        d.loc[mask, "_time_used"] = d.loc[mask, "_runtime_seconds"] / d.loc[mask, "_budget_seconds"]
        time_agg = d.groupby(["competition_id"] + config_cols, dropna=False).agg(
            runtime_mean_seconds=("_runtime_seconds", "mean"),
            mean_time_used=("_time_used", "mean"),
        )
        time_agg = time_agg.reset_index()
        attempts = attempts.merge(time_agg, on=["competition_id"] + config_cols, how="left")

    successes = d[d["status"] == "success"].copy()
    if successes.empty:
        return pd.DataFrame()

    med = successes.groupby(["competition_id"] + config_cols, dropna=False).agg(
        score_norm_median=("_score_norm", "median"),
        score_norm_q25=("_score_norm", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.25))),
        score_norm_q75=("_score_norm", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.75))),
    )
    med = med.reset_index()

    # Rank within each competition by median score.
    med["_configs_in_comp"] = med.groupby("competition_id")["score_norm_median"].transform("size")
    med["rank"] = med.groupby("competition_id")["score_norm_median"].rank(ascending=False, method="min")
    med["rank_pct"] = 0.0
    mask = med["_configs_in_comp"] > 1
    med.loc[mask, "rank_pct"] = (med.loc[mask, "rank"] - 1.0) / (med.loc[mask, "_configs_in_comp"] - 1.0)

    # Merge attempts so we can treat failures as worst rank (100%) for "expected" rank.
    per_comp = attempts.merge(med, on=["competition_id"] + config_cols, how="left")
    per_comp["had_success"] = per_comp["run_success"] > 0
    per_comp["rank_pct_success_only"] = per_comp["rank_pct"].where(per_comp["had_success"], pd.NA)
    per_comp["rank_pct_expected"] = per_comp["rank_pct"].where(per_comp["had_success"], 1.0)

    # Aggregate across competitions per config.
    out = per_comp.groupby(config_cols, dropna=False).agg(
        competitions_attempted=("competition_id", "nunique"),
        competitions_succeeded=("had_success", "sum"),
        runs=("runs", "sum"),
        run_success=("run_success", "sum"),
        run_success_rate=("run_success_rate", "mean"),
        mean_rank_pct_success_only=("rank_pct_success_only", "mean"),
        mean_rank_pct_expected=("rank_pct_expected", "mean"),
        rank_pct_p25=("rank_pct_expected", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.25))),
        rank_pct_p50=("rank_pct_expected", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.50))),
        rank_pct_p75=("rank_pct_expected", lambda s: float(pd.to_numeric(s, errors="coerce").quantile(0.75))),
    )
    out = out.reset_index()
    out["competition_success_rate"] = out["competitions_succeeded"] / out["competitions_attempted"].replace(0, pd.NA)

    if "runtime_mean_seconds" in per_comp.columns:
        rt = per_comp.groupby(config_cols, dropna=False).agg(
            runtime_mean_seconds=("runtime_mean_seconds", "mean"),
            mean_time_used=("mean_time_used", "mean"),
        )
        out = out.merge(rt.reset_index(), on=config_cols, how="left")

    # Baseline-normalized absolute signal using median score_norm per competition.
    if (
        baselines is not None
        and not baselines.empty
        and {"competition_id", "baseline_type", "score_normalized"}.issubset(set(baselines.columns))
    ):
        b = baselines.copy()
        b["competition_id"] = b["competition_id"].fillna("").astype(str)
        b["baseline_type"] = b["baseline_type"].fillna("").astype(str)
        b["score_normalized"] = pd.to_numeric(b["score_normalized"], errors="coerce")
        pivot = (
            b.pivot_table(index="competition_id", columns="baseline_type", values="score_normalized", aggfunc="max")
            .reset_index()
            .rename(columns={"constant": "baseline_constant_norm", "hgb": "baseline_hgb_norm"})
        )
        per_abs = med.merge(pivot, on="competition_id", how="left")
        if "baseline_constant_norm" in per_abs.columns and "baseline_hgb_norm" in per_abs.columns:
            den = per_abs["baseline_hgb_norm"] - per_abs["baseline_constant_norm"]
            per_abs["abs_units_median"] = (per_abs["score_norm_median"] - per_abs["baseline_constant_norm"]) / den.replace(0, pd.NA)
            per_abs.loc[den <= 0, "abs_units_median"] = pd.NA
            per_abs["beat_hgb"] = (per_abs["score_norm_median"] > per_abs["baseline_hgb_norm"]).astype("Int64")
            abs_agg = per_abs.groupby(config_cols, dropna=False).agg(
                competitions_abs=("abs_units_median", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
                mean_abs_units=("abs_units_median", "mean"),
                median_abs_units=("abs_units_median", "median"),
                beat_hgb=("beat_hgb", "sum"),
            )
            abs_agg = abs_agg.reset_index()
            abs_agg["beat_hgb_rate"] = abs_agg["beat_hgb"] / abs_agg["competitions_abs"].replace(0, pd.NA)
            out = out.merge(abs_agg, on=config_cols, how="left")

    # Formatting
    out["mean_rank_pct_success_only"] = pd.to_numeric(out["mean_rank_pct_success_only"], errors="coerce").round(4)
    out["mean_rank_pct_expected"] = pd.to_numeric(out["mean_rank_pct_expected"], errors="coerce").round(4)
    out["rank_pct_p25"] = pd.to_numeric(out["rank_pct_p25"], errors="coerce").round(4)
    out["rank_pct_p50"] = pd.to_numeric(out["rank_pct_p50"], errors="coerce").round(4)
    out["rank_pct_p75"] = pd.to_numeric(out["rank_pct_p75"], errors="coerce").round(4)
    out["competition_success_rate"] = pd.to_numeric(out["competition_success_rate"], errors="coerce").round(4)
    out["run_success_rate"] = pd.to_numeric(out["run_success_rate"], errors="coerce").round(4)
    if "runtime_mean_seconds" in out.columns:
        out["runtime_mean_seconds"] = pd.to_numeric(out["runtime_mean_seconds"], errors="coerce").round(1)
    if "mean_time_used" in out.columns:
        out["mean_time_used"] = pd.to_numeric(out["mean_time_used"], errors="coerce").round(4)
    if "mean_abs_units" in out.columns:
        out["mean_abs_units"] = pd.to_numeric(out["mean_abs_units"], errors="coerce").round(3)
    if "median_abs_units" in out.columns:
        out["median_abs_units"] = pd.to_numeric(out["median_abs_units"], errors="coerce").round(3)
    if "beat_hgb_rate" in out.columns:
        out["beat_hgb_rate"] = pd.to_numeric(out["beat_hgb_rate"], errors="coerce").round(4)

    def _pct(x: object) -> str:
        try:
            v = float(x)
            if pd.isna(v):
                return ""
            return f"{100.0 * v:.1f}%"
        except Exception:  # noqa: BLE001
            return ""

    out["competition_success_rate"] = out["competition_success_rate"].map(_pct)
    out["run_success_rate"] = out["run_success_rate"].map(_pct)
    out["mean_rank_pct_success_only"] = out["mean_rank_pct_success_only"].map(_pct)
    out["mean_rank_pct_expected"] = out["mean_rank_pct_expected"].map(_pct)
    out["rank_pct_p25"] = out["rank_pct_p25"].map(_pct)
    out["rank_pct_p50"] = out["rank_pct_p50"].map(_pct)
    out["rank_pct_p75"] = out["rank_pct_p75"].map(_pct)
    if "mean_time_used" in out.columns:
        out["mean_time_used"] = out["mean_time_used"].map(_pct)
    if "beat_hgb_rate" in out.columns:
        out["beat_hgb_rate"] = out["beat_hgb_rate"].map(_pct)

    cols = config_cols + [
        "competitions_attempted",
        "competitions_succeeded",
        "competition_success_rate",
        "runs",
        "run_success",
        "run_success_rate",
        "runtime_mean_seconds",
        "mean_time_used",
        "mean_rank_pct_success_only",
        "mean_rank_pct_expected",
        "rank_pct_p25",
        "rank_pct_p50",
        "rank_pct_p75",
        "competitions_abs",
        "mean_abs_units",
        "median_abs_units",
        "beat_hgb_rate",
    ]
    cols = [c for c in cols if c in out.columns]
    out = out[cols]

    out["_sort_rank_pct"] = pd.to_numeric(
        out["mean_rank_pct_expected"].astype(str).str.replace("%", "", regex=False),
        errors="coerce",
    )
    out = out.sort_values(by=["_sort_rank_pct", "competitions_succeeded"], ascending=[True, False], na_position="last")
    out = out.drop(columns=["_sort_rank_pct"])
    return out


def write_root_leaderboard_robust(*, df: pd.DataFrame, repo_root: Path, baselines: pd.DataFrame | None = None) -> None:
    """
    Writes an additional, more robust view alongside the default leaderboard:
    - Root: `LEADERBOARD_ROBUST.md` / `LEADERBOARD_ROBUST.html`
    - Results: `results/leaderboard_robust.{json,csv,html}`
    """
    md_path = repo_root / "LEADERBOARD_ROBUST.md"
    html_path = repo_root / "LEADERBOARD_ROBUST.html"
    out_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard_robust.json",
        csv_path=repo_root / "results" / "leaderboard_robust.csv",
        html_path=repo_root / "results" / "leaderboard_robust.html",
    )

    # Keep the same raw runs export for convenience, but under a different filename.
    # (This is just the df input serialized.)
    out_paths.json_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.csv_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.html_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.json_path.write_text(df.to_json(orient="records", indent=2, double_precision=15), encoding="utf-8")
    df.to_csv(out_paths.csv_path, index=False, quoting=csv.QUOTE_MINIMAL, float_format="%.15g")
    out_paths.html_path.write_text(df.to_html(index=False, escape=True), encoding="utf-8")

    title = "TML-bench leaderboard (robust view)"
    md = "# TML-bench leaderboard (robust view)\n\n"
    md += "This file is generated by the orchestrator from local run results.\n\n"
    md += "- Source DB (not committed): `results/results.sqlite`\n"
    md += "- Also generated: `results/leaderboard_robust.json`, `results/leaderboard_robust.csv`, `results/leaderboard_robust.html`\n\n"
    md += f"- Timestamps are in US Pacific (`{_pacific_tz_name()}`)\n\n"

    if df.empty or not {"competition_id", "provider", "model_id", "run_id"}.issubset(set(df.columns)):
        md += "_No runs found._\n"
        md_path.write_text(md, encoding="utf-8")
        html_path.write_text(f"<h1>{title}</h1><p>No runs found.</p>", encoding="utf-8")
        return

    df_sorted = df.copy()
    df_sorted["score_raw"] = pd.to_numeric(df_sorted.get("score_raw"), errors="coerce")
    df_sorted["_score_norm"] = _score_normalized_series(df_sorted)
    df_sorted["_runnable_model"] = [
        _is_runnable_model(provider=p, model_id=m) for p, m in zip(df_sorted["provider"], df_sorted["model_id"], strict=False)
    ]
    if "created_at" in df_sorted.columns:
        df_sorted["_created_at_dt"] = df_sorted["created_at"].map(_parse_iso_datetime)
    df_sorted = df_sorted.sort_values(
        by=["competition_id", "_score_norm", "_created_at_dt" if "_created_at_dt" in df_sorted.columns else "created_at"],
        ascending=[True, False, False],
        na_position="last",
    )

    overall = _overall_by_model_robust_df(df_sorted[df_sorted["_runnable_model"]], baselines=baselines)
    if not overall.empty:
        md += "## Overall (robust; median-of-successes)\n\n"
        md += (
            "- Per competition/config uses the **median** normalized score over successful runs (not best-of).\n"
            "- `mean_rank_pct_expected` treats competitions with no success as worst (100%) to incorporate reliability.\n"
            "- `rank_pct_p25/p50/p75` shows spread across competitions (lower is better).\n\n"
        )
        if baselines is not None and not baselines.empty:
            md += "- Absolute signal uses two fixed host baselines per competition: `constant` and `hgb`.\n"
            md += "  - `mean_abs_units`: 0 = constant baseline, 1 = hgb baseline (higher is better).\n\n"

        if "prompt_profile" not in overall.columns:
            md += _df_to_markdown_table(overall.head(60))
        else:
            known = ["simple-baseline", "good-baseline", "sota-xgb"]
            present_known = [p for p in known if (overall["prompt_profile"] == p).any()]
            present_other = sorted(
                {
                    str(x)
                    for x in overall["prompt_profile"].astype(str).tolist()
                    if str(x) and str(x) not in set(known)
                }
            )
            has_legacy = (overall["prompt_profile"].astype(str).str.strip() == "").any()

            def _emit_profile_md(profile_label: str, dfp: pd.DataFrame) -> None:
                nonlocal md
                if dfp.empty:
                    return
                md += f"### {profile_label}\n\n"
                if "prompt_profile" in dfp.columns:
                    dfp = dfp.drop(columns=["prompt_profile"])
                md += _df_to_markdown_table(dfp.head(60))

            for p in present_known:
                _emit_profile_md(p, overall[overall["prompt_profile"] == p])
            for p in present_other:
                _emit_profile_md(p, overall[overall["prompt_profile"] == p])
            if has_legacy:
                _emit_profile_md("(legacy/unspecified)", overall[overall["prompt_profile"].astype(str).str.strip() == ""])

    md += "## Duplicate submissions (by config + normalized hash)\n\n"
    dup = _duplicate_submissions_df(
        df_sorted[df_sorted["_runnable_model"]],
        group_cols=["competition_id", "budget_time_seconds", "prompt_profile"],
    )
    md += _df_to_markdown_table(dup) if not dup.empty else "_(none)_\n"

    md += "\n## Variance (per model/config)\n\n"
    var = _variance_df(
        df_sorted[df_sorted["_runnable_model"]],
        group_cols=["competition_id", "provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"],
    )
    md += _df_to_markdown_table(var) if not var.empty else "_(none)_\n"

    md += "\n## All runs\n\n"
    df_display = df_sorted[df_sorted["_runnable_model"]].copy()
    for col in ["_created_at_dt", "_runnable_model", "_score_norm"]:
        if col in df_display.columns:
            df_display = df_display.drop(columns=[col])
    md += _df_to_markdown_table(df_display)
    md_path.write_text(md, encoding="utf-8")

    html = (
        f"<h1>{title}</h1>\n"
        "<p>Generated by the orchestrator from local run results.</p>\n"
        "<ul>"
        "<li>Source DB (not committed): <code>results/results.sqlite</code></li>"
        "<li>Also generated: <code>results/leaderboard_robust.json</code>, <code>results/leaderboard_robust.csv</code>, <code>results/leaderboard_robust.html</code></li>"
        f"<li>Timestamps are in US Pacific (<code>{_pacific_tz_name()}</code>)</li>"
        "</ul>\n"
    )
    if not overall.empty:
        html += "\n<h2>Overall (robust; median-of-successes)</h2>\n"
        html += (
            "<p>Per competition/config uses the <b>median</b> normalized score over successful runs (not best-of). "
            "<code>mean_rank_pct_expected</code> treats competitions with no success as worst (100%) to incorporate reliability. "
            "<code>rank_pct_p25/p50/p75</code> shows spread across competitions.</p>\n"
        )
        if baselines is not None and not baselines.empty:
            html += (
                "<p>Absolute signal uses two fixed host baselines per competition: <code>constant</code> and <code>hgb</code>. "
                "<code>mean_abs_units</code>: 0 = constant baseline, 1 = hgb baseline.</p>\n"
            )
        if "prompt_profile" not in overall.columns:
            html += overall.head(60).to_html(index=False, escape=True)
        else:
            known = ["simple-baseline", "good-baseline", "sota-xgb"]
            present_known = [p for p in known if (overall["prompt_profile"] == p).any()]
            present_other = sorted(
                {
                    str(x)
                    for x in overall["prompt_profile"].astype(str).tolist()
                    if str(x) and str(x) not in set(known)
                }
            )
            has_legacy = (overall["prompt_profile"].astype(str).str.strip() == "").any()

            def _emit_profile_html(profile_label: str, dfp: pd.DataFrame) -> None:
                nonlocal html
                if dfp.empty:
                    return
                html += f"\n<h3>{profile_label}</h3>\n"
                if "prompt_profile" in dfp.columns:
                    dfp = dfp.drop(columns=["prompt_profile"])
                html += dfp.head(60).to_html(index=False, escape=True)

            for p in present_known:
                _emit_profile_html(p, overall[overall["prompt_profile"] == p])
            for p in present_other:
                _emit_profile_html(p, overall[overall["prompt_profile"] == p])
            if has_legacy:
                _emit_profile_html("(legacy/unspecified)", overall[overall["prompt_profile"].astype(str).str.strip() == ""])

    html += "<h2>Duplicate submissions (by config + normalized hash)</h2>\n"
    html += dup.to_html(index=False, escape=True) if not dup.empty else "<p><i>(none)</i></p>\n"
    html += "\n<h2>Variance (per model/config)</h2>\n"
    html += var.to_html(index=False, escape=True) if not var.empty else "<p><i>(none)</i></p>\n"
    html += "\n<h2>All runs</h2>\n"
    html += df_display.to_html(index=False, escape=True)
    html_path.write_text(html, encoding="utf-8")


def _duplicate_submissions_df(df: pd.DataFrame, *, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    needed = {"run_id", "provider", "model_id", "status", "score_raw", "normalized_submission_sha256"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()

    d = df.copy()
    d = d.fillna("")
    d = d[(d["status"] == "success") & (d["normalized_submission_sha256"].astype(str).str.strip() != "")]
    if d.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    gb_cols = [c for c in group_cols if c in d.columns] + ["normalized_submission_sha256"]
    if not gb_cols or "normalized_submission_sha256" not in gb_cols:
        return pd.DataFrame()

    for keys, g in d.groupby(gb_cols, dropna=False):
        n = int(len(g))
        if n <= 1:
            continue
        g = g.copy()
        g["score_raw"] = pd.to_numeric(g["score_raw"], errors="coerce")
        g = g.sort_values(by=["score_raw", "run_id"], ascending=[True, True], na_position="last")

        models = [f"{p}::{m}" for p, m in zip(g["provider"].astype(str), g["model_id"].astype(str), strict=False)]
        run_ids = [str(x) for x in g["run_id"].tolist()]
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_map = {col: val for col, val in zip(gb_cols, keys, strict=False)}
        rows.append(
            {
                **{k: ("" if k == "normalized_submission_sha256" else str(v)) for k, v in key_map.items() if k != "normalized_submission_sha256"},
                "normalized_submission_sha256": str(key_map.get("normalized_submission_sha256", "")),
                "count": n,
                "score_raw": float(g["score_raw"].iloc[0]) if pd.notna(g["score_raw"].iloc[0]) else "",
                "models": ", ".join(models[:5]) + ("…" if n > 5 else ""),
                "run_ids": ", ".join(run_ids[:5]) + ("…" if n > 5 else ""),
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    sort_cols = []
    for c in group_cols:
        if c in out.columns:
            sort_cols.append(c)
    out = out.sort_values(by=sort_cols + ["count"], ascending=[True] * len(sort_cols) + [False], na_position="last")
    return out


def _variance_df(df: pd.DataFrame, *, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    needed = {"status", "score_raw", "normalized_submission_sha256"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()

    d = df.copy()
    d = d.fillna("")
    d = d[d["status"] == "success"]
    if d.empty:
        return pd.DataFrame()
    d["score_raw"] = pd.to_numeric(d["score_raw"], errors="coerce")
    d = d[pd.notna(d["score_raw"])]
    if d.empty:
        return pd.DataFrame()

    gb_cols = [c for c in group_cols if c in d.columns]
    if not gb_cols:
        return pd.DataFrame()

    def _uniq_nonempty(s: pd.Series) -> int:
        vals = [str(x).strip() for x in s.tolist()]
        return len({v for v in vals if v})

    agg = d.groupby(gb_cols, dropna=False).agg(
        runs=("score_raw", "size"),
        score_min=("score_raw", "min"),
        score_mean=("score_raw", "mean"),
        score_max=("score_raw", "max"),
        score_std=("score_raw", "std"),
        unique_normalized_submissions=("normalized_submission_sha256", _uniq_nonempty),
    )
    out = agg.reset_index()
    return out.sort_values(by=gb_cols + ["score_mean"], ascending=[True] * len(gb_cols) + [True], na_position="last")


def write_root_leaderboard(
    *, df: pd.DataFrame, repo_root: Path, title: str = "TML-bench leaderboard", baselines: pd.DataFrame | None = None
) -> None:
    md_path = repo_root / "LEADERBOARD.md"
    html_path = repo_root / "LEADERBOARD.html"

    df_display = df

    md = (
        f"# {title}\n\n"
        "This file is generated by the orchestrator from local run results.\n\n"
        "- Source DB (not committed): `results/results.sqlite`\n"
        "- Also generated: `results/leaderboard.json`, `results/leaderboard.csv`, `results/leaderboard.html`\n\n"
        f"- Timestamps are in US Pacific (`{_pacific_tz_name()}`)\n\n"
    )
    if not df.empty and {"competition_id", "provider", "model_id", "mode", "score_raw", "run_id"}.issubset(set(df.columns)):
        df_sorted = df.copy()
        df_sorted["score_raw"] = pd.to_numeric(df_sorted["score_raw"], errors="coerce")
        df_sorted["_score_norm"] = _score_normalized_series(df_sorted)
        df_sorted["_runnable_model"] = [
            _is_runnable_model(provider=p, model_id=m) for p, m in zip(df_sorted["provider"], df_sorted["model_id"], strict=False)
        ]
        if "created_at" in df_sorted.columns:
            df_sorted["_created_at_dt"] = df_sorted["created_at"].map(_parse_iso_datetime)
        df_sorted = df_sorted.sort_values(
            by=["competition_id", "_score_norm", "_created_at_dt" if "_created_at_dt" in df_sorted.columns else "created_at"],
            ascending=[True, False, False],
            na_position="last",
        )
        best_src = df_sorted[df_sorted["_runnable_model"]].copy()
        if "status" in best_src.columns:
            best_src = best_src[best_src["status"] == "success"]
        group_cols = ["competition_id", "provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"]
        group_cols = [c for c in group_cols if c in best_src.columns]
        best = best_src.groupby(group_cols, dropna=False).head(1).copy()
        if "_created_at_dt" in best.columns:
            best = best.drop(columns=["_created_at_dt"])
        if "_runnable_model" in best.columns:
            best = best.drop(columns=["_runnable_model"])
        best = best.rename(
            columns={
                "run_id": "best_run_id",
                "score_raw": "best_score_raw",
                "runtime_seconds": "best_runtime_seconds",
                "budget_time_seconds": "budget_time_seconds",
            }
        )
        if "secondary_r2" in best.columns:
            best = best.rename(columns={"secondary_r2": "best_secondary_r2"})
        if "submission_sha256" in best.columns:
            best = best.rename(columns={"submission_sha256": "best_submission_sha256"})
        if "normalized_submission_sha256" in best.columns:
            best = best.rename(columns={"normalized_submission_sha256": "best_normalized_submission_sha256"})

        best_cols = [
            "competition_id",
            "provider",
            "model_id",
            "mode",
            "prompt_profile",
            "metric_name",
            "best_score_raw",
            "best_secondary_r2",
            "best_runtime_seconds",
            "budget_time_seconds",
            "best_run_id",
        ]
        best_cols = [c for c in best_cols if c in best.columns]
        for extra in ["best_submission_sha256", "best_normalized_submission_sha256"]:
            if extra in best.columns:
                best_cols.append(extra)
        best = best[best_cols]

        overall = _overall_by_model_df(df_sorted[df_sorted["_runnable_model"]], baselines=baselines)
        if not overall.empty:
            md += "## Overall (across competitions)\n\n"
            md += (
                "- Ranks are computed per competition using each model/config’s best normalized score (higher-is-better). "
                "`mean_rank_pct` is a percentile rank within each competition (0% is best).\n"
                "- Aggregation is shown separately per `prompt_profile`.\n\n"
            )
            md += "- Per-competition `*_mean` columns show mean `score_raw` over successful runs for the core 4 competitions.\n\n"
            if baselines is not None and not baselines.empty:
                md += "- Absolute signal uses two fixed host baselines per competition: `constant` and `hgb`.\n"
                md += "  - `mean_abs_units`: 0 = constant baseline, 1 = hgb baseline (higher is better).\n"
                md += "  - `beat_hgb_rate`: fraction of competitions where the model beats the hgb baseline.\n\n"

            if "prompt_profile" not in overall.columns:
                md += _df_to_markdown_table(overall.head(60))
            else:
                known = ["simple-baseline", "good-baseline"]
                present_known = [p for p in known if (overall["prompt_profile"] == p).any()]
                present_other = sorted(
                    {
                        str(x)
                        for x in overall["prompt_profile"].astype(str).tolist()
                        if str(x) and str(x) not in set(known)
                    }
                )
                has_legacy = (overall["prompt_profile"].astype(str).str.strip() == "").any()

                def _emit_profile_md(profile_label: str, dfp: pd.DataFrame) -> None:
                    nonlocal md
                    if dfp.empty:
                        return
                    md += f"### {profile_label}\n\n"
                    if "prompt_profile" in dfp.columns:
                        dfp = dfp.drop(columns=["prompt_profile"])
                    md += _df_to_markdown_table(dfp.head(60))

                for p in present_known:
                    _emit_profile_md(p, overall[overall["prompt_profile"] == p])
                for p in present_other:
                    _emit_profile_md(p, overall[overall["prompt_profile"] == p])
                if has_legacy:
                    _emit_profile_md("(legacy/unspecified)", overall[overall["prompt_profile"].astype(str).str.strip() == ""])
        md += "## Best by model (per competition)\n\n"
        md += _df_to_markdown_table(best)

        dup = _duplicate_submissions_df(
            df_sorted[df_sorted["_runnable_model"]],
            group_cols=["competition_id", "budget_time_seconds", "prompt_profile"],
        )
        if not dup.empty:
            md += "\n## Duplicate submissions (by config + normalized hash)\n\n"
            md += _df_to_markdown_table(dup)

        var = _variance_df(
            df_sorted[df_sorted["_runnable_model"]],
            group_cols=["competition_id", "provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"],
        )
        if not var.empty:
            md += "\n## Variance (per model/config)\n\n"
            md += _df_to_markdown_table(var)

        md += "\n## All runs\n\n"
        df_display = df_sorted[df_sorted["_runnable_model"]].copy()
        for col in ["_created_at_dt", "_runnable_model", "_score_norm"]:
            if col in df_display.columns:
                df_display = df_display.drop(columns=[col])
    md += _df_to_markdown_table(df_display)
    md_path.write_text(md, encoding="utf-8")

    html = (
        f"<h1>{title}</h1>\n"
        "<p>Generated by the orchestrator from local run results.</p>\n"
        "<ul>"
        "<li>Source DB (not committed): <code>results/results.sqlite</code></li>"
        "<li>Also generated: <code>results/leaderboard.json</code>, <code>results/leaderboard.csv</code>, <code>results/leaderboard.html</code></li>"
        f"<li>Timestamps are in US Pacific (<code>{_pacific_tz_name()}</code>)</li>"
        "</ul>\n"
    )
    if not df.empty and {"competition_id", "provider", "model_id", "mode", "score_raw", "run_id"}.issubset(set(df.columns)):
        df_sorted = df.copy()
        df_sorted["score_raw"] = pd.to_numeric(df_sorted["score_raw"], errors="coerce")
        df_sorted["_score_norm"] = _score_normalized_series(df_sorted)
        df_sorted["_runnable_model"] = [
            _is_runnable_model(provider=p, model_id=m) for p, m in zip(df_sorted["provider"], df_sorted["model_id"], strict=False)
        ]
        if "created_at" in df_sorted.columns:
            df_sorted["_created_at_dt"] = df_sorted["created_at"].map(_parse_iso_datetime)
        df_sorted = df_sorted.sort_values(
            by=["competition_id", "_score_norm", "_created_at_dt" if "_created_at_dt" in df_sorted.columns else "created_at"],
            ascending=[True, False, False],
            na_position="last",
        )
        best_src = df_sorted[df_sorted["_runnable_model"]].copy()
        if "status" in best_src.columns:
            best_src = best_src[best_src["status"] == "success"]
        group_cols = ["competition_id", "provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"]
        group_cols = [c for c in group_cols if c in best_src.columns]
        best = best_src.groupby(group_cols, dropna=False).head(1).copy()
        if "_created_at_dt" in best.columns:
            best = best.drop(columns=["_created_at_dt"])
        if "_runnable_model" in best.columns:
            best = best.drop(columns=["_runnable_model"])
        best = best.rename(
            columns={
                "run_id": "best_run_id",
                "score_raw": "best_score_raw",
                "runtime_seconds": "best_runtime_seconds",
            }
        )
        if "secondary_r2" in best.columns:
            best = best.rename(columns={"secondary_r2": "best_secondary_r2"})
        if "submission_sha256" in best.columns:
            best = best.rename(columns={"submission_sha256": "best_submission_sha256"})
        if "normalized_submission_sha256" in best.columns:
            best = best.rename(columns={"normalized_submission_sha256": "best_normalized_submission_sha256"})

        overall = _overall_by_model_df(df_sorted[df_sorted["_runnable_model"]], baselines=baselines)
        if not overall.empty:
            html += "\n<h2>Overall (across competitions)</h2>\n"
            html += (
                "<p>Ranks are computed per competition using each model/config’s best normalized score (higher-is-better). "
                "<code>mean_rank_pct</code> is a percentile rank within each competition (0% is best). "
                "Aggregation is shown separately per <code>prompt_profile</code>.</p>\n"
            )
            if baselines is not None and not baselines.empty:
                html += (
                    "<p>Absolute signal uses two fixed host baselines per competition: <code>constant</code> and <code>hgb</code>. "
                    "<code>mean_abs_units</code>: 0 = constant baseline, 1 = hgb baseline (higher is better). "
                    "<code>beat_hgb_rate</code>: fraction of competitions where the model beats the hgb baseline.</p>\n"
                )
            if "prompt_profile" not in overall.columns:
                html += overall.head(60).to_html(index=False, escape=True)
            else:
                known = ["simple-baseline", "good-baseline"]
                present_known = [p for p in known if (overall["prompt_profile"] == p).any()]
                present_other = sorted(
                    {
                        str(x)
                        for x in overall["prompt_profile"].astype(str).tolist()
                        if str(x) and str(x) not in set(known)
                    }
                )
                has_legacy = (overall["prompt_profile"].astype(str).str.strip() == "").any()

                def _emit_profile_html(profile_label: str, dfp: pd.DataFrame) -> None:
                    nonlocal html
                    if dfp.empty:
                        return
                    html += f"\n<h3>{profile_label}</h3>\n"
                    if "prompt_profile" in dfp.columns:
                        dfp = dfp.drop(columns=["prompt_profile"])
                    html += dfp.head(60).to_html(index=False, escape=True)

                for p in present_known:
                    _emit_profile_html(p, overall[overall["prompt_profile"] == p])
                for p in present_other:
                    _emit_profile_html(p, overall[overall["prompt_profile"] == p])
                if has_legacy:
                    _emit_profile_html("(legacy/unspecified)", overall[overall["prompt_profile"].astype(str).str.strip() == ""])

        html += "<h2>Best by model (per competition)</h2>\n"
        best_cols = [
            "competition_id",
            "provider",
            "model_id",
            "mode",
            "prompt_profile",
            "metric_name",
            "best_score_raw",
            "best_secondary_r2",
            "best_runtime_seconds",
            "budget_time_seconds",
            "best_run_id",
        ]
        best_cols = [c for c in best_cols if c in best.columns]
        for extra in ["best_submission_sha256", "best_normalized_submission_sha256"]:
            if extra in best.columns:
                best_cols.append(extra)
        html += best[best_cols].to_html(index=False, escape=True)

        dup = _duplicate_submissions_df(
            df_sorted[df_sorted["_runnable_model"]],
            group_cols=["competition_id", "budget_time_seconds", "prompt_profile"],
        )
        if not dup.empty:
            html += "\n<h2>Duplicate submissions (by config + normalized hash)</h2>\n"
            html += dup.to_html(index=False, escape=True)

        var = _variance_df(
            df_sorted[df_sorted["_runnable_model"]],
            group_cols=["competition_id", "provider", "model_id", "mode", "budget_time_seconds", "prompt_profile"],
        )
        if not var.empty:
            html += "\n<h2>Variance (per model/config)</h2>\n"
            html += var.to_html(index=False, escape=True)

        html += "\n<h2>All runs</h2>\n"

    html += df_display.to_html(index=False, escape=True)
    html_path.write_text(html, encoding="utf-8")


def build_leaderboard(
    *,
    db_path: Path,
    out_paths: LeaderboardPaths,
    competition_id: str | None = None,
) -> pd.DataFrame:
    ensure_db(db_path)
    rows = fetch_runs(db_path, competition_id=competition_id)
    df_full = pd.DataFrame(rows)
    keep = [
        "run_id",
        "created_at",
        "competition_id",
        "status",
        "provider",
        "model_id",
        "mode",
        "prompt_profile",
        "temperature",
        "max_tokens",
        "metric_name",
        "score_raw",
        "score_normalized",
        "secondary_r2",
        "runtime_seconds",
        "budget_time_seconds",
        "time_used_frac",
        "seed",
        "submission_sha256",
        "normalized_submission_sha256",
    ]
    if df_full.empty:
        df = pd.DataFrame(columns=keep)
    else:
        df = df_full[[c for c in keep if c in df_full.columns]].copy()

    if "runtime_seconds" in df.columns:
        df["runtime_seconds"] = pd.to_numeric(df["runtime_seconds"], errors="coerce")
    if "budget_time_seconds" in df.columns:
        df["budget_time_seconds"] = pd.to_numeric(df["budget_time_seconds"], errors="coerce")

    if "runtime_seconds" in df.columns and "budget_time_seconds" in df.columns:
        mask = df["runtime_seconds"].notna() & df["budget_time_seconds"].notna() & (df["budget_time_seconds"] > 0)
        df["time_used_frac"] = pd.NA
        df.loc[mask, "time_used_frac"] = df.loc[mask, "runtime_seconds"] / df.loc[mask, "budget_time_seconds"]
        df["time_used_frac"] = pd.to_numeric(df["time_used_frac"], errors="coerce").round(4)

    # Sorting is done using parsed datetimes, but we display in US Pacific.
    if "created_at" in df.columns:
        df["_created_at_dt"] = df["created_at"].map(_parse_iso_datetime)

    # Sort using normalized score (higher-is-better) when possible.
    df["score_raw"] = pd.to_numeric(df.get("score_raw"), errors="coerce")
    df["score_normalized"] = _score_normalized_series(df)
    sort_created = "_created_at_dt" if "_created_at_dt" in df.columns else "created_at"
    df = df.sort_values(by=["competition_id", "score_normalized", sort_created], ascending=[True, False, False], na_position="last")

    if "created_at" in df.columns:
        df["created_at"] = df["created_at"].map(_format_created_at_pacific)
        if "_created_at_dt" in df.columns:
            df = df.drop(columns=["_created_at_dt"])

    def _short_sha(x: object) -> object:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return ""
        return s[:16] + "…"

    if "submission_sha256" in df.columns:
        df["submission_sha256"] = df["submission_sha256"].map(_short_sha)
    if "normalized_submission_sha256" in df.columns:
        df["normalized_submission_sha256"] = df["normalized_submission_sha256"].map(_short_sha)

    out_paths.json_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.csv_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.html_path.parent.mkdir(parents=True, exist_ok=True)

    out_paths.json_path.write_text(df.to_json(orient="records", indent=2, double_precision=15), encoding="utf-8")
    df.to_csv(out_paths.csv_path, index=False, quoting=csv.QUOTE_MINIMAL, float_format="%.15g")

    out_paths.html_path.write_text(df.to_html(index=False, escape=True), encoding="utf-8")

    return df


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate leaderboard files from the local results DB.")
    parser.add_argument("--db-path", default="results/results.sqlite")
    parser.add_argument("--competition-id", default=None)
    parser.add_argument("--per-competition", action="store_true", help="If set, leaderboard is filtered to --competition-id.")
    parser.add_argument("--write-root", action="store_true", help="If set, write LEADERBOARD.md/html at repo root.")
    parser.add_argument(
        "--import-results",
        action="store_true",
        help="If set, (re)import all `runs/*/result.json` into the DB before generating the leaderboard.",
    )
    parser.add_argument("--runs-root", default="runs", help="Path to the runs/ directory for --import-results.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = Path(args.db_path)

    if args.import_results:
        runs_root = Path(args.runs_root)
        imported = 0
        for run_dir in sorted(runs_root.glob("*")):
            if not run_dir.is_dir():
                continue
            result_path = run_dir / "result.json"
            if not result_path.exists():
                continue
            try:
                rr = read_result_json(result_path)
            except Exception:
                continue
            if args.per_competition and args.competition_id and rr.competition_id != args.competition_id:
                continue
            insert_run(db_path, rr)
            imported += 1
        print(f"imported results into DB: {imported}")

    out_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard.json",
        csv_path=repo_root / "results" / "leaderboard.csv",
        html_path=repo_root / "results" / "leaderboard.html",
    )
    df = build_leaderboard(
        db_path=db_path,
        out_paths=out_paths,
        competition_id=args.competition_id if args.per_competition else None,
    )
    if args.write_root:
        baselines_df = load_baselines_df(db_path=db_path)
        write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)
        write_root_leaderboard_robust(df=df, repo_root=repo_root, baselines=baselines_df)
    print(f"wrote: {out_paths.json_path}")
    print(f"wrote: {out_paths.csv_path}")
    print(f"wrote: {out_paths.html_path}")
    if args.write_root:
        print(f"wrote: {repo_root / 'LEADERBOARD.md'}")
        print(f"wrote: {repo_root / 'LEADERBOARD.html'}")
        print(f"wrote: {repo_root / 'LEADERBOARD_ROBUST.md'}")
        print(f"wrote: {repo_root / 'LEADERBOARD_ROBUST.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
