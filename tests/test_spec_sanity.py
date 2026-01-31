from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from orchestrator.db import ensure_db
from orchestrator.spec_sanity import build_monotonic_report


def _insert_run(
    con: sqlite3.Connection,
    *,
    run_id: str,
    competition_id: str,
    prompt_profile: str,
    budget: int,
    provider: str,
    model_id: str,
    mode: str,
    status: str,
    metric_name: str,
    score_raw: float,
) -> None:
    con.execute(
        """
        INSERT INTO runs (
          run_id, created_at, competition_id, status,
          metric_name, score_raw, score_normalized, local_validation_metric,
          runtime_seconds, budget_time_seconds, seed, prompt_profile,
          provider, model_id, mode, temperature, max_tokens,
          submission_path, normalized_submission_path,
          submission_sha256, normalized_submission_sha256,
          spec_sha256, prompt_sha256, public_manifest_sha256, kilo_version, kilo_config_sha256,
          benchmark_version, git_sha, git_dirty
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            "2026-01-30T00:00:00Z",
            competition_id,
            status,
            metric_name,
            float(score_raw),
            float(score_raw) if metric_name == "auc" else -float(score_raw),
            None,
            1.0,
            int(budget),
            1,
            prompt_profile,
            provider,
            model_id,
            mode,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
    )


def test_spec_sanity_monotonic_flags(tmp_path: Path) -> None:
    # Minimal DB with 4 suite competitions and 2 models.
    db_path = tmp_path / "results.sqlite"
    ensure_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        core = [
            "bank-customer-churn-ict-u-ai",
            "foot-traffic-wuerzburg-retail-forecasting-2-0",
            "playground-series-s5e10",
            "playground-series-s6e1",
        ]
        specs = [("simple-baseline", 240), ("good-baseline", 600), ("sota-xgb", 1200)]

        # Model A improves monotonically (lower rmse -> better normalized).
        for i, (profile, budget) in enumerate(specs):
            for j, comp in enumerate(core):
                _insert_run(
                    con,
                    run_id=f"a_{i}_{j}",
                    competition_id=comp,
                    prompt_profile=profile,
                    budget=budget,
                    provider="p",
                    model_id="A",
                    mode="",
                    status="success",
                    metric_name="rmse",
                    score_raw=10.0 - i,  # 10, 9, 8
                )

        # Model B gets worse at sota.
        for i, (profile, budget) in enumerate(specs):
            for j, comp in enumerate(core):
                score = 10.0 - i
                if profile == "sota-xgb":
                    score = 20.0  # worse
                _insert_run(
                    con,
                    run_id=f"b_{i}_{j}",
                    competition_id=comp,
                    prompt_profile=profile,
                    budget=budget,
                    provider="p",
                    model_id="B",
                    mode="",
                    status="success",
                    metric_name="rmse",
                    score_raw=score,
                )

        con.commit()
    finally:
        con.close()

    report = build_monotonic_report(db_path=db_path, suite="v5_core", join_mode="strict")
    assert not report.empty
    # Expect two rows.
    assert set(report["model_id"]) == {"A", "B"}

    a = report[report["model_id"] == "A"].iloc[0]
    b = report[report["model_id"] == "B"].iloc[0]
    assert bool(a["rank_monotonic"]) is True
    assert bool(b["rank_monotonic"]) is False


def test_spec_sanity_prompt_profile_override(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    ensure_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        core = [
            "bank-customer-churn-ict-u-ai",
            "foot-traffic-wuerzburg-retail-forecasting-2-0",
            "playground-series-s5e10",
            "playground-series-s6e1",
        ]
        budgets = [240, 600, 1200]
        profile = "budget-aware"
        for i, budget in enumerate(budgets):
            for j, comp in enumerate(core):
                _insert_run(
                    con,
                    run_id=f"m_{i}_{j}",
                    competition_id=comp,
                    prompt_profile=profile,
                    budget=budget,
                    provider="p",
                    model_id="M",
                    mode="",
                    status="success",
                    metric_name="rmse",
                    score_raw=10.0 - i,
                )
        con.commit()
    finally:
        con.close()

    report = build_monotonic_report(
        db_path=db_path,
        suite="v5_core",
        join_mode="strict",
        prompt_profile_override="budget-aware",
    )
    assert not report.empty
    assert set(report["model_id"]) == {"M"}
