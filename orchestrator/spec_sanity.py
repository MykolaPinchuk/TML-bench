from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from orchestrator.db import ensure_db, fetch_runs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _df_to_markdown_table(df: pd.DataFrame) -> str:
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


def _load_suite_competitions(suite: str) -> list[str]:
    p = _repo_root() / "orchestrator" / "suites" / f"{suite}.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing suite file: {p}")
    import json

    raw = json.loads(p.read_text(encoding="utf-8"))
    comps = raw.get("competitions")
    if not isinstance(comps, list) or not comps:
        raise ValueError(f"Invalid suite file (missing competitions list): {p}")
    out: list[str] = []
    for c in comps:
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
    if not out:
        raise ValueError(f"Invalid suite file (empty competitions): {p}")
    return out


def _score_norm(series: pd.Series, metric: pd.Series) -> pd.Series:
    raw = pd.to_numeric(series, errors="coerce")
    m = metric.fillna("").astype(str).str.strip().str.lower()
    higher_is_better = m.isin(["auc"])
    out = raw.copy()
    out[~higher_is_better] = -raw[~higher_is_better]
    return out


def build_spec_profile_summary(
    *,
    db_path: str | Path,
    competitions: list[str],
    prompt_profile: str,
    budget_seconds: int,
    join_mode: str = "strict",
) -> pd.DataFrame:
    """
    Build a per-model summary for one (prompt_profile, budget_seconds) spec.

    join_mode:
      - strict: keep (provider, model_id, mode) as the config key
      - best: collapse modes by taking best median score per competition (then rank)
    """
    ensure_db(db_path)
    rows = fetch_runs(db_path)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for c in ["competition_id", "status", "provider", "model_id", "mode", "prompt_profile", "metric_name"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    df = df[df["competition_id"].isin(set(competitions))].copy()
    df = df[(df["prompt_profile"] == str(prompt_profile)) & (df["budget_time_seconds"] == int(budget_seconds))].copy()
    if df.empty:
        return pd.DataFrame()

    config_cols = ["provider", "model_id"]
    if join_mode == "strict":
        config_cols.append("mode")
    elif join_mode == "best":
        pass
    else:
        raise ValueError("join_mode must be one of: strict, best")

    for c in config_cols:
        df[c] = df[c].fillna("").astype(str)

    # Attempts per (competition, config).
    attempts = (
        df.groupby(["competition_id"] + config_cols, dropna=False)
        .agg(
            runs=("run_id", "count"),
            run_success=("status", lambda s: int((s == "success").sum())),
        )
        .reset_index()
    )
    attempts["run_success_rate"] = attempts["run_success"] / attempts["runs"].replace(0, pd.NA)

    successes = df[df["status"] == "success"].copy()
    if successes.empty:
        per_comp = attempts.copy()
        per_comp["rank_pct_expected"] = 1.0
    else:
        successes["_score_norm"] = _score_norm(successes.get("score_raw"), successes.get("metric_name"))
        med = (
            successes.groupby(["competition_id"] + config_cols, dropna=False)
            .agg(score_norm_median=("_score_norm", "median"))
            .reset_index()
        )

        if join_mode == "best":
            # Collapse modes by taking the best median score per (competition, provider, model_id).
            med = (
                med.groupby(["competition_id", "provider", "model_id"], dropna=False)
                .agg(score_norm_median=("score_norm_median", "max"))
                .reset_index()
            )
            attempts = (
                attempts.groupby(["competition_id", "provider", "model_id"], dropna=False)
                .agg(
                    runs=("runs", "sum"),
                    run_success=("run_success", "sum"),
                    run_success_rate=("run_success_rate", "mean"),
                )
                .reset_index()
            )
            config_cols = ["provider", "model_id"]

        med["_configs_in_comp"] = med.groupby("competition_id")["score_norm_median"].transform("size")
        med["rank"] = med.groupby("competition_id")["score_norm_median"].rank(ascending=False, method="min")
        med["rank_pct"] = 0.0
        mask = med["_configs_in_comp"] > 1
        med.loc[mask, "rank_pct"] = (med.loc[mask, "rank"] - 1.0) / (med.loc[mask, "_configs_in_comp"] - 1.0)

        per_comp = attempts.merge(med, on=["competition_id"] + config_cols, how="left")
        per_comp["had_success"] = per_comp["run_success"] > 0
        per_comp["rank_pct_expected"] = per_comp["rank_pct"].where(per_comp["had_success"], 1.0)

    out = (
        per_comp.groupby(config_cols, dropna=False)
        .agg(
            competitions_attempted=("competition_id", "nunique"),
            competitions_succeeded=("had_success", "sum") if "had_success" in per_comp.columns else ("competition_id", "count"),
            runs=("runs", "sum"),
            run_success=("run_success", "sum"),
            run_success_rate=("run_success_rate", "mean"),
            mean_rank_pct_expected=("rank_pct_expected", "mean"),
        )
        .reset_index()
    )
    out["competition_success_rate"] = out["competitions_succeeded"] / out["competitions_attempted"].replace(0, pd.NA)
    out["prompt_profile"] = str(prompt_profile)
    out["budget_time_seconds"] = int(budget_seconds)
    return out


def build_monotonic_report(
    *,
    db_path: str | Path,
    suite: str,
    join_mode: str = "strict",
    prompt_profile_override: str | None = None,
) -> pd.DataFrame:
    competitions = _load_suite_competitions(suite)
    specs = [
        ("s-b", "simple-baseline", 240),
        ("g-b", "good-baseline", 600),
        ("sota", "sota-xgb", 1200),
    ]
    if prompt_profile_override is not None:
        specs = [(label, str(prompt_profile_override), budget) for (label, _profile, budget) in specs]

    frames: list[pd.DataFrame] = []
    for label, profile, budget in specs:
        s = build_spec_profile_summary(
            db_path=db_path,
            competitions=competitions,
            prompt_profile=profile,
            budget_seconds=budget,
            join_mode=join_mode,
        )
        if s.empty:
            continue
        s = s.copy()
        s["spec"] = label
        frames.append(s)
    if not frames:
        return pd.DataFrame()

    d = pd.concat(frames, ignore_index=True)
    key_cols = ["provider", "model_id"] + (["mode"] if (join_mode == "strict" and "mode" in d.columns) else [])

    # Keep only keys that have all 3 specs represented.
    have = d.groupby(key_cols, dropna=False)["spec"].nunique().reset_index(name="n_specs")
    keep = have[have["n_specs"] == 3][key_cols]
    if keep.empty:
        return pd.DataFrame()
    d = d.merge(keep, on=key_cols, how="inner")

    pv = d.pivot_table(index=key_cols, columns="spec", values=["mean_rank_pct_expected", "run_success_rate"], aggfunc="first")
    pv.columns = [f"{a}__{b}" for (a, b) in pv.columns]
    pv = pv.reset_index()

    def _monotonic_rank(row: pd.Series) -> bool:
        # Lower is better, so we expect s-b >= g-b >= sota.
        a = row.get("mean_rank_pct_expected__s-b")
        b = row.get("mean_rank_pct_expected__g-b")
        c = row.get("mean_rank_pct_expected__sota")
        if pd.isna(a) or pd.isna(b) or pd.isna(c):
            return False
        return bool((float(a) >= float(b)) and (float(b) >= float(c)))

    pv["rank_monotonic"] = pv.apply(_monotonic_rank, axis=1)
    pv = pv.sort_values(by=["mean_rank_pct_expected__sota"], ascending=[True], na_position="last")
    return pv


def _pct(x: object) -> str:
    try:
        v = float(x)
    except Exception:
        return ""
    if pd.isna(v):
        return ""
    return f"{100.0 * v:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description="Sanity-check monotonic progress across the 3 canonical specs.")
    ap.add_argument("--db-path", default=str(_repo_root() / "results" / "results.sqlite"))
    ap.add_argument("--suite", default="v5_core", help="Suite id (file in orchestrator/suites/<suite>.json).")
    ap.add_argument(
        "--join-mode",
        default="strict",
        choices=["strict", "best"],
        help="strict: compare (provider, model_id, mode); best: collapse modes per model (best median per competition).",
    )
    ap.add_argument(
        "--prompt-profile",
        default=None,
        help="If set, use this prompt profile for all three budgets (240/600/1200) to run a fixed-prompt sanity check.",
    )
    ap.add_argument("--out-md", default=None, help="If set, write Markdown report to this path.")
    args = ap.parse_args()

    df = build_monotonic_report(
        db_path=args.db_path,
        suite=args.suite,
        join_mode=args.join_mode,
        prompt_profile_override=(str(args.prompt_profile).strip() if args.prompt_profile else None),
    )
    title = f"Spec sanity ({args.suite}, join_mode={args.join_mode})"
    md = f"# {title}\n\n"
    md += f"- db: `{args.db_path}`\n"
    md += "- specs:\n"
    md += "  - s-b = (simple-baseline, 240s)\n"
    md += "  - g-b = (good-baseline, 600s)\n"
    md += "  - sota = (sota-xgb, 1200s)\n\n"

    if df.empty:
        md += "_No comparable models found across all 3 specs._\n"
    else:
        # Format a small, readable table.
        show = df.copy()
        for c in [c for c in show.columns if c.startswith("mean_rank_pct_expected__")]:
            show[c] = show[c].map(_pct)
        for c in [c for c in show.columns if c.startswith("run_success_rate__")]:
            show[c] = show[c].map(_pct)
        md += f"- comparable models: {len(show)}\n"
        md += f"- rank_monotonic rate: {show['rank_monotonic'].mean():.3f}\n\n"
        cols = [c for c in ["provider", "model_id", "mode"] if c in show.columns]
        cols += [
            "rank_monotonic",
            "mean_rank_pct_expected__s-b",
            "mean_rank_pct_expected__g-b",
            "mean_rank_pct_expected__sota",
            "run_success_rate__s-b",
            "run_success_rate__g-b",
            "run_success_rate__sota",
        ]
        cols = [c for c in cols if c in show.columns]
        md += _df_to_markdown_table(show[cols]) + "\n"

    print(md, end="")
    if args.out_md:
        out_path = Path(args.out_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"\nwrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
