from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.async_suite_runner import _blocked_models_by_recent_failures


def _create_runs_table(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              competition_id TEXT NOT NULL,
              status TEXT NOT NULL,
              budget_time_seconds INTEGER,
              prompt_profile TEXT,
              prompt_strategy TEXT,
              provider TEXT,
              model_id TEXT,
              mode TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _insert_run(
    db_path: Path,
    *,
    run_id: str,
    created_at: datetime,
    competition_id: str,
    status: str,
    provider: str,
    model_id: str,
    prompt_profile: str = "simple-baseline",
    prompt_strategy: str = "profiled1",
    mode: str = "topup",
    budget_time_seconds: int = 240,
) -> None:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO runs
            (run_id, created_at, competition_id, status, budget_time_seconds, prompt_profile, prompt_strategy, provider, model_id, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at.isoformat(timespec="seconds"),
                competition_id,
                status,
                budget_time_seconds,
                prompt_profile,
                prompt_strategy,
                provider,
                model_id,
                mode,
            ),
        )
        con.commit()
    finally:
        con.close()


def test_blocked_models_by_recent_failures_uses_consecutive_streak(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    _create_runs_table(db_path)
    now = datetime.now(timezone.utc)

    # Model A: three recent failures in a row -> blocked.
    _insert_run(
        db_path,
        run_id="a1",
        created_at=now - timedelta(minutes=20),
        competition_id="c1",
        status="timeout",
        provider="chutes",
        model_id="model-a",
    )
    _insert_run(
        db_path,
        run_id="a2",
        created_at=now - timedelta(minutes=15),
        competition_id="c2",
        status="runtime_error",
        provider="chutes",
        model_id="model-a",
    )
    _insert_run(
        db_path,
        run_id="a3",
        created_at=now - timedelta(minutes=10),
        competition_id="c1",
        status="timeout",
        provider="chutes",
        model_id="model-a",
    )

    # Model B: recent success breaks the failure streak -> not blocked.
    _insert_run(
        db_path,
        run_id="b1",
        created_at=now - timedelta(minutes=30),
        competition_id="c1",
        status="timeout",
        provider="chutes",
        model_id="model-b",
    )
    _insert_run(
        db_path,
        run_id="b2",
        created_at=now - timedelta(minutes=25),
        competition_id="c1",
        status="success",
        provider="chutes",
        model_id="model-b",
    )
    _insert_run(
        db_path,
        run_id="b3",
        created_at=now - timedelta(minutes=5),
        competition_id="c2",
        status="timeout",
        provider="chutes",
        model_id="model-b",
    )

    blocked, details = _blocked_models_by_recent_failures(
        db_path=db_path,
        prompt_profile="simple-baseline",
        prompt_strategy="profiled1",
        mode="topup",
        budget_seconds=240,
        failure_threshold=3,
        window_hours=24,
    )

    assert ("chutes", "model-a") in blocked
    assert ("chutes", "model-b") not in blocked
    assert details[("chutes", "model-a")]["consecutive_failures"] == 3

