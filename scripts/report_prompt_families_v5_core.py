#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RunRow:
    family: str
    source_db: str
    run_id: str
    created_at: str
    competition_id: str
    budget_time_seconds: int
    provider: str
    model_id: str
    status: str
    metric_name: str | None
    score_raw: float | None
    score_normalized: float | None
    runtime_seconds: float | None
    prompt_profile: str | None
    git_sha: str | None


@dataclass(frozen=True)
class AggRow:
    competition_id: str
    budget_time_seconds: int
    metric_name: str
    family: str
    n_total: int
    n_success: int
    mean_raw_success: float | None
    best_raw_success: float | None


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _mean(xs: Iterable[float]) -> float | None:
    xs = list(xs)
    if not xs:
        return None
    return sum(xs) / len(xs)


def _best(xs: Iterable[float], *, metric_name: str) -> float | None:
    xs = list(xs)
    if not xs:
        return None
    if metric_name.lower() in {"rmse", "mae", "logloss", "mse"}:
        return min(xs)
    return max(xs)


def _direction(metric_name: str) -> str:
    if metric_name.lower() in {"rmse", "mae", "logloss", "mse"}:
        return "lower"
    return "higher"


def _improvement(baseline: float | None, other: float | None, *, metric_name: str) -> float | None:
    if baseline is None or other is None:
        return None
    if _direction(metric_name) == "lower":
        return baseline - other
    return other - baseline


def _load_models_5(models_path: Path) -> list[str]:
    data = json.loads(models_path.read_text())
    models = data.get("models", [])
    model_ids = [m["model_id"] for m in models if m.get("provider") == "chutes"]
    if len(model_ids) != 5:
        raise SystemExit(f"expected 5 chutes models in {models_path}, got {len(model_ids)}")
    return model_ids


def _query_runs(db_path: Path, *, family: str, where_sql: str, params: list[Any]) -> list[RunRow]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        rows = cur.execute(
            f"""
            SELECT
              run_id, created_at, competition_id, budget_time_seconds,
              provider, model_id, status, metric_name, score_raw, score_normalized,
              runtime_seconds, prompt_profile, git_sha
            FROM runs
            WHERE {where_sql}
            """,
            params,
        ).fetchall()
    finally:
        con.close()

    out: list[RunRow] = []
    for r in rows:
        out.append(
            RunRow(
                family=family,
                source_db=str(db_path),
                run_id=r[0],
                created_at=r[1],
                competition_id=r[2],
                budget_time_seconds=int(r[3]),
                provider=r[4],
                model_id=r[5],
                status=r[6],
                metric_name=r[7],
                score_raw=r[8],
                score_normalized=r[9],
                runtime_seconds=r[10],
                prompt_profile=r[11],
                git_sha=r[12],
            )
        )
    return out


def _dedupe_latest(rows: list[RunRow]) -> list[RunRow]:
    latest: dict[tuple[str, int, str, str], RunRow] = {}
    # key = (family, budget, competition, model)
    for r in rows:
        key = (r.family, r.budget_time_seconds, r.competition_id, r.model_id)
        cur = latest.get(key)
        if cur is None or _dt(r.created_at) > _dt(cur.created_at):
            latest[key] = r
    return list(latest.values())


def _aggregate(rows: list[RunRow], *, comps: list[str], budgets: list[int], families: list[str]) -> list[AggRow]:
    grouped: dict[tuple[str, int, str], list[RunRow]] = {}
    for r in rows:
        grouped.setdefault((r.competition_id, r.budget_time_seconds, r.family), []).append(r)

    out: list[AggRow] = []
    for comp in comps:
        for budget in budgets:
            for family in families:
                rs = grouped.get((comp, budget, family), [])
                metric = next((x.metric_name for x in rs if x.metric_name), None) or "unknown"
                succ = [x for x in rs if x.status == "success" and x.score_raw is not None]
                raw_scores = [float(x.score_raw) for x in succ]
                out.append(
                    AggRow(
                        competition_id=comp,
                        budget_time_seconds=budget,
                        metric_name=metric,
                        family=family,
                        n_total=len(rs),
                        n_success=len(succ),
                        mean_raw_success=_mean(raw_scores),
                        best_raw_success=_best(raw_scores, metric_name=metric),
                    )
                )
    return out


def main() -> int:
    suite = [
        "bank-customer-churn-ict-u-ai",
        "foot-traffic-wuerzburg-retail-forecasting-2-0",
        "playground-series-s5e10",
        "playground-series-s6e1",
    ]
    budgets = [240, 600, 1200]
    families = ["baseline", "time-gated", "budget-aware"]

    models_path = REPO_ROOT / "orchestrator" / "model_sets" / "v3_fast.json"
    model_ids_5 = _load_models_5(models_path)

    baseline_shas = {
        240: "9276a569f43c19e22be92dcabcae0222b8485c15",
        600: "f41af8d21a5e3fda3827b0d2b890f121d9a98028",
        1200: "3baf1d094169b1a9497d473fa3e34d3bd371a0bf",
    }
    baseline_prompt_profile = {240: "simple-baseline", 600: "good-baseline", 1200: "sota-xgb"}

    db_baseline_history = REPO_ROOT / "results" / "results.sqlite"
    db_baseline_patch = REPO_ROOT / "results" / "exp_promptfam_baseline_patch.sqlite"
    db_timegated = REPO_ROOT / "results" / "exp_promptfam_timegated.sqlite"
    db_budgetaware = REPO_ROOT / "results" / "exp_promptfam_budgetaware.sqlite"

    if not db_baseline_history.exists():
        raise SystemExit(f"missing baseline history db: {db_baseline_history}")
    for p in [db_baseline_patch, db_timegated, db_budgetaware]:
        if not p.exists():
            raise SystemExit(f"missing db: {p}")

    # Baseline from history (pinned git_sha per budget).
    clauses: list[str] = []
    params: list[Any] = []
    for b in budgets:
        sha = baseline_shas[b]
        pp = baseline_prompt_profile[b]
        clauses.append("(git_sha=? AND budget_time_seconds=? AND prompt_profile=?)")
        params += [sha, b, pp]
    where = "provider='chutes' AND competition_id IN ({}) AND model_id IN ({}) AND ({})".format(
        ",".join("?" * len(suite)),
        ",".join("?" * len(model_ids_5)),
        " OR ".join(clauses),
    )
    baseline_rows = _query_runs(
        db_baseline_history,
        family="baseline",
        where_sql=where,
        params=suite + model_ids_5 + params,
    )

    # Baseline patch override (missing ps-s6e1 @ 600).
    baseline_patch_rows = _query_runs(
        db_baseline_patch,
        family="baseline",
        where_sql="provider='chutes' AND competition_id IN ({}) AND model_id IN ({})".format(
            ",".join("?" * len(suite)),
            ",".join("?" * len(model_ids_5)),
        ),
        params=suite + model_ids_5,
    )

    # Other families.
    timegated_rows = _query_runs(
        db_timegated,
        family="time-gated",
        where_sql="provider='chutes' AND competition_id IN ({}) AND model_id IN ({})".format(
            ",".join("?" * len(suite)),
            ",".join("?" * len(model_ids_5)),
        ),
        params=suite + model_ids_5,
    )
    budgetaware_rows = _query_runs(
        db_budgetaware,
        family="budget-aware",
        where_sql="provider='chutes' AND competition_id IN ({}) AND model_id IN ({})".format(
            ",".join("?" * len(suite)),
            ",".join("?" * len(model_ids_5)),
        ),
        params=suite + model_ids_5,
    )

    all_rows = _dedupe_latest(baseline_rows + timegated_rows + budgetaware_rows)

    # Override baseline with patch rows for any overlapping tuples.
    patch_dedup = _dedupe_latest(baseline_patch_rows)
    patch_keys = {(r.family, r.budget_time_seconds, r.competition_id, r.model_id) for r in patch_dedup}
    all_rows = [r for r in all_rows if (r.family, r.budget_time_seconds, r.competition_id, r.model_id) not in patch_keys]
    all_rows.extend(patch_dedup)

    # Write per-run CSV (post-dedupe/override).
    out_runs_csv = REPO_ROOT / "results" / "exp_promptfam_comparison_runs.csv"
    out_runs_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_runs_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "family",
                "source_db",
                "run_id",
                "created_at",
                "competition_id",
                "budget_time_seconds",
                "provider",
                "model_id",
                "status",
                "metric_name",
                "score_raw",
                "score_normalized",
                "runtime_seconds",
                "prompt_profile",
                "git_sha",
            ]
        )
        for r in sorted(all_rows, key=lambda x: (x.family, x.budget_time_seconds, x.competition_id, x.model_id)):
            w.writerow(
                [
                    r.family,
                    r.source_db,
                    r.run_id,
                    r.created_at,
                    r.competition_id,
                    r.budget_time_seconds,
                    r.provider,
                    r.model_id,
                    r.status,
                    r.metric_name,
                    r.score_raw,
                    r.score_normalized,
                    r.runtime_seconds,
                    r.prompt_profile,
                    r.git_sha,
                ]
            )

    # Aggregate rows and write summary CSV.
    agg = _aggregate(all_rows, comps=suite, budgets=budgets, families=families)
    out_sum_csv = REPO_ROOT / "results" / "exp_promptfam_comparison_summary.csv"
    with out_sum_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "competition_id",
                "budget_time_seconds",
                "metric_name",
                "family",
                "n_success",
                "n_total",
                "mean_raw_success",
                "best_raw_success",
                "direction",
            ]
        )
        for a in agg:
            w.writerow(
                [
                    a.competition_id,
                    a.budget_time_seconds,
                    a.metric_name,
                    a.family,
                    a.n_success,
                    a.n_total,
                    a.mean_raw_success,
                    a.best_raw_success,
                    _direction(a.metric_name),
                ]
            )

    # Markdown table (per competition/budget).
    def key(a: AggRow) -> tuple[str, int, str]:
        return (a.competition_id, a.budget_time_seconds, a.family)

    by = {key(a): a for a in agg}
    out_md = REPO_ROOT / "docs" / "experiments" / "prompt_family_comparison_v5_core.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    def fmt(x: float | None, metric: str) -> str:
        if x is None:
            return "—"
        if metric.lower() == "auc":
            return f"{x:.6f}"
        if metric.lower() == "rmse":
            return f"{x:.6f}"
        return f"{x:.6f}"

    lines: list[str] = []
    lines.append("# Prompt Family Comparison (v5_core)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("Scope: v5_core suite (4 competitions), 5 Chutes models, runs-per-model=1, concurrency=2.")
    lines.append("")
    lines.append("Families / sources:")
    lines.append(f"- Baseline: `results/results.sqlite` filtered to pinned `git_sha` per budget + patch from `results/exp_promptfam_baseline_patch.sqlite`.")
    lines.append(f"- Time-gated: `results/exp_promptfam_timegated.sqlite`.")
    lines.append(f"- Budget-aware: `results/exp_promptfam_budgetaware.sqlite`.")
    lines.append("")
    lines.append("Aggregation notes:")
    lines.append("- `mean`/`best` are computed over **successful** runs only (so timeouts don’t get an artificial score).")
    lines.append("- `Δ vs baseline` is computed on the raw metric with `better > 0` (e.g. RMSE uses `baseline - other`, AUC uses `other - baseline`).")
    lines.append("")

    header = (
        "| competition | metric | budget | baseline succ/5 | baseline mean | time-gated succ/5 | time-gated mean | Δ vs base | "
        "budget-aware succ/5 | budget-aware mean | Δ vs base |"
    )
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines.append(header)
    lines.append(sep)

    for comp in suite:
        for budget in budgets:
            base = by[(comp, budget, "baseline")]
            metric = base.metric_name
            tg = by.get((comp, budget, "time-gated"))
            ba = by.get((comp, budget, "budget-aware"))
            if tg is not None and tg.n_total == 0:
                tg = None
            if ba is not None and ba.n_total == 0:
                ba = None

            base_mean = base.mean_raw_success
            tg_mean = tg.mean_raw_success if tg else None
            ba_mean = ba.mean_raw_success if ba else None

            tg_delta = _improvement(base_mean, tg_mean, metric_name=metric) if tg else None
            ba_delta = _improvement(base_mean, ba_mean, metric_name=metric) if ba else None

            def succ(a: AggRow | None) -> str:
                if a is None:
                    return "—"
                if a.n_total == 0:
                    return "—"
                return f"{a.n_success}/{a.n_total}"

            row = [
                comp,
                metric,
                str(budget),
                succ(base),
                fmt(base_mean, metric),
                succ(tg),
                fmt(tg_mean, metric),
                "—" if tg is None else (fmt(tg_delta, metric) if tg_delta is not None else "—"),
                succ(ba),
                fmt(ba_mean, metric),
                fmt(ba_delta, metric) if ba_delta is not None else "—",
            ]
            lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("Artifacts:")
    lines.append(f"- Per-run rows: `results/exp_promptfam_comparison_runs.csv`")
    lines.append(f"- Aggregated summary: `results/exp_promptfam_comparison_summary.csv`")

    out_md.write_text("\n".join(lines) + "\n")
    print(f"wrote: {out_md}")
    print(f"wrote: {out_runs_csv}")
    print(f"wrote: {out_sum_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
