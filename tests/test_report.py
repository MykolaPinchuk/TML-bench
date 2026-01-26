from __future__ import annotations

import sqlite3
from pathlib import Path

from orchestrator.db import ensure_db
from orchestrator.report import build_health_report


def test_health_report_basic(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    ensure_db(db_path)

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO runs (run_id, created_at, competition_id, status, provider, model_id, budget_time_seconds, prompt_profile) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("r1", "2026-01-01T00:00:00+00:00", "c1", "success", "p", "m", 240, "simple-baseline"),
        )
        con.execute(
            "INSERT INTO runs (run_id, created_at, competition_id, status, provider, model_id, budget_time_seconds, prompt_profile) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("r2", "2026-01-02T00:00:00+00:00", "c1", "timeout", "p", "m", 240, "simple-baseline"),
        )
        con.commit()
    finally:
        con.close()

    health, failures, meta = build_health_report(db_path=db_path)
    assert meta["runs_total"] == 2
    assert meta["runs_success"] == 1
    assert meta["runs_failed"] == 1

    assert len(health) == 1
    row = health.iloc[0].to_dict()
    assert row["competition_id"] == "c1"
    assert row["provider"] == "p"
    assert row["model_id"] == "m"
    assert row["success_rate"] == "50.0%"
    assert row["timeout_rate"] == "50.0%"

    assert failures is not None
    assert not failures.empty

