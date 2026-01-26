from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from orchestrator.db import ensure_db, fetch_runs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    df = df.fillna("")
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


def _pct(n: float) -> str:
    return f"{100.0 * float(n):.1f}%"


def build_health_report(
    *, db_path: str | Path, competition_id: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    ensure_db(db_path)
    rows = fetch_runs(db_path, competition_id=competition_id)
    if not rows:
        return pd.DataFrame(), pd.DataFrame(), {"runs_total": 0, "runs_success": 0, "runs_failed": 0}

    df = pd.DataFrame(rows)
    if "created_at" in df.columns:
        df["_created_at_dt"] = df["created_at"].map(_parse_iso_datetime)
    if "runtime_seconds" in df.columns:
        df["runtime_seconds"] = pd.to_numeric(df["runtime_seconds"], errors="coerce")
    if "score_normalized" in df.columns:
        df["score_normalized"] = pd.to_numeric(df["score_normalized"], errors="coerce")

    group_cols = ["competition_id", "provider", "model_id", "budget_time_seconds", "prompt_profile"]
    group_cols = [c for c in group_cols if c in df.columns]
    if not group_cols:
        group_cols = ["competition_id"] if "competition_id" in df.columns else []
    if not group_cols:
        return pd.DataFrame(), pd.DataFrame(), {"runs_total": 0, "runs_success": 0, "runs_failed": 0}

    runs_total = int(len(df))
    runs_success = int((df["status"] == "success").sum()) if "status" in df.columns else 0
    runs_failed = runs_total - runs_success

    d = df.copy()
    for c in group_cols:
        d[c] = d[c].fillna("").astype(str)
    if "status" in d.columns:
        d["status"] = d["status"].fillna("").astype(str)

    def _count_status(s: pd.Series, name: str) -> int:
        return int((s.astype(str) == name).sum())

    agg = d.groupby(group_cols, dropna=False).agg(
        runs=("run_id", "count"),
        success=("status", lambda s: _count_status(s, "success")),
        timeout=("status", lambda s: _count_status(s, "timeout")),
        invalid_submission=("status", lambda s: _count_status(s, "invalid_submission")),
        runtime_error=("status", lambda s: _count_status(s, "runtime_error")),
        other=("status", lambda s: int((~s.astype(str).isin({"success", "timeout", "invalid_submission", "runtime_error"})).sum())),
        runtime_mean_seconds=("runtime_seconds", "mean") if "runtime_seconds" in d.columns else ("run_id", "count"),
        best_score_normalized=("score_normalized", "max") if "score_normalized" in d.columns else ("run_id", "count"),
        last_created_at=("_created_at_dt", "max") if "_created_at_dt" in d.columns else ("created_at", "max"),
    )

    out = agg.reset_index()
    out["success_rate"] = out["success"] / out["runs"]
    out["timeout_rate"] = out["timeout"] / out["runs"]
    out["invalid_rate"] = out["invalid_submission"] / out["runs"]
    out["runtime_error_rate"] = out["runtime_error"] / out["runs"]

    if "runtime_mean_seconds" in out.columns:
        out["runtime_mean_seconds"] = pd.to_numeric(out["runtime_mean_seconds"], errors="coerce").round(1)
    if "best_score_normalized" in out.columns:
        out["best_score_normalized"] = pd.to_numeric(out["best_score_normalized"], errors="coerce")
        out["best_score_normalized"] = out["best_score_normalized"].round(6)

    if "last_created_at" in out.columns:
        out["last_created_at"] = out["last_created_at"].map(lambda x: x.isoformat() if isinstance(x, datetime) else str(x))

    cols_keep = group_cols + [
        "runs",
        "success_rate",
        "timeout_rate",
        "invalid_rate",
        "runtime_error_rate",
        "runtime_mean_seconds",
        "best_score_normalized",
        "last_created_at",
    ]
    cols_keep = [c for c in cols_keep if c in out.columns]
    out = out[cols_keep]

    for c in ["success_rate", "timeout_rate", "invalid_rate", "runtime_error_rate"]:
        if c in out.columns:
            out[c] = out[c].map(_pct)

    sort_cols = [c for c in group_cols if c in out.columns]
    if sort_cols:
        out = out.sort_values(by=sort_cols, ascending=[True] * len(sort_cols), na_position="last")

    failures = df.copy()
    failures = failures[failures["status"] != "success"] if "status" in failures.columns else failures.iloc[0:0]
    if failures.empty:
        return out, pd.DataFrame(), {"runs_total": runs_total, "runs_success": runs_success, "runs_failed": runs_failed}

    fail_group_cols = [c for c in group_cols if c in failures.columns]
    for c in fail_group_cols:
        failures[c] = failures[c].fillna("").astype(str)
    failures["_created_at_dt"] = failures["created_at"].map(_parse_iso_datetime) if "created_at" in failures.columns else None
    fail = failures.groupby(fail_group_cols + ["status"], dropna=False).agg(
        count=("run_id", "count"),
        last_run_id=("run_id", "max"),
        last_created_at=("_created_at_dt", "max"),
    )
    fail = fail.reset_index().sort_values(by=["count"], ascending=[False], na_position="last")
    if "last_created_at" in fail.columns:
        fail["last_created_at"] = fail["last_created_at"].map(lambda x: x.isoformat() if isinstance(x, datetime) else str(x))
    return out, fail, {"runs_total": runs_total, "runs_success": runs_success, "runs_failed": runs_failed}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run health report from results/results.sqlite.")
    ap.add_argument("--db-path", default=str(_repo_root() / "results" / "results.sqlite"))
    ap.add_argument("--competition-id", default=None)
    ap.add_argument("--out-md", default=None, help="If set, write a Markdown report to this path.")
    ap.add_argument("--top-failures", type=int, default=30)
    args = ap.parse_args()

    health, failures, meta = build_health_report(db_path=args.db_path, competition_id=args.competition_id)
    title = "Run health report"
    if args.competition_id:
        title += f" ({args.competition_id})"

    md = f"# {title}\n\n"
    md += f"- db: `{args.db_path}`\n"
    md += f"- runs_total: {meta.get('runs_total', 0)}\n"
    md += f"- runs_success: {meta.get('runs_success', 0)}\n"
    md += f"- runs_failed: {meta.get('runs_failed', 0)}\n"
    md += f"- groups: {0 if health is None or health.empty else int(len(health))}\n\n"

    if health.empty:
        md += "_No runs found._\n"
    else:
        md += "## By model/config\n\n"
        md += _df_to_markdown_table(health)

    if failures is not None and not failures.empty:
        md += "\n## Top failures\n\n"
        top = failures.head(int(args.top_failures)).copy()
        md += _df_to_markdown_table(top)

    print(md, end="")
    if args.out_md:
        out_path = Path(args.out_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"\nwrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
