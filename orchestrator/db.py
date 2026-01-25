from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from orchestrator.result import RunResult


def ensure_db(db_path: str | Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              competition_id TEXT NOT NULL,
              status TEXT NOT NULL,
              metric_name TEXT,
              score_raw REAL,
              score_normalized REAL,
              local_validation_metric REAL,
              runtime_seconds REAL,
              budget_time_seconds INTEGER,
              provider TEXT,
              model_id TEXT,
              mode TEXT,
              temperature REAL,
              max_tokens INTEGER,
              submission_path TEXT,
              normalized_submission_path TEXT,
              submission_sha256 TEXT,
              normalized_submission_sha256 TEXT,
              spec_sha256 TEXT,
              prompt_sha256 TEXT,
              public_manifest_sha256 TEXT,
              kilo_version TEXT,
              kilo_config_sha256 TEXT,
              benchmark_version TEXT,
              git_sha TEXT,
              git_dirty INTEGER
            )
            """
        )
        # Backward-compatible migrations (in case DB existed before columns were added).
        cols = {row[1] for row in con.execute("PRAGMA table_info(runs)").fetchall()}
        if "runtime_seconds" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN runtime_seconds REAL")
        if "budget_time_seconds" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN budget_time_seconds INTEGER")
        if "provider" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN provider TEXT")
        if "model_id" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN model_id TEXT")
        if "mode" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN mode TEXT")
        if "temperature" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN temperature REAL")
        if "max_tokens" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN max_tokens INTEGER")
        if "submission_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN submission_sha256 TEXT")
        if "normalized_submission_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN normalized_submission_sha256 TEXT")
        if "spec_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN spec_sha256 TEXT")
        if "prompt_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN prompt_sha256 TEXT")
        if "public_manifest_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN public_manifest_sha256 TEXT")
        if "kilo_version" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN kilo_version TEXT")
        if "kilo_config_sha256" not in cols:
            con.execute("ALTER TABLE runs ADD COLUMN kilo_config_sha256 TEXT")
        con.commit()
    finally:
        con.close()


def _to_int_bool(x: bool | None) -> int | None:
    if x is None:
        return None
    return 1 if x else 0


def insert_run(db_path: str | Path, run: RunResult) -> None:
    ensure_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        artifacts = run.artifacts
        versions = run.versions
        model = run.model
        notes = artifacts.notes if artifacts else None
        submission_sha256 = None
        normalized_submission_sha256 = None
        spec_sha256 = None
        prompt_sha256 = None
        public_manifest_sha256 = None
        kilo_version = None
        kilo_config_sha256 = None
        if isinstance(notes, dict):
            submission_sha256 = notes.get("submission_sha256")
            normalized_submission_sha256 = notes.get("normalized_submission_sha256")
            # Backward-compatible: allow older result.json to store provenance in notes.
            spec_sha256 = notes.get("spec_sha256")
            prompt_sha256 = notes.get("prompt_sha256")
            public_manifest_sha256 = notes.get("public_manifest_sha256")
            kilo_version = notes.get("kilo_version")
            kilo_config_sha256 = notes.get("kilo_config_sha256")

        if run.provenance is not None:
            spec_sha256 = run.provenance.spec_sha256 or spec_sha256
            prompt_sha256 = run.provenance.prompt_sha256 or prompt_sha256
            public_manifest_sha256 = run.provenance.public_manifest_sha256 or public_manifest_sha256
            kilo_version = run.provenance.kilo_version or kilo_version
            kilo_config_sha256 = run.provenance.kilo_config_sha256 or kilo_config_sha256
        con.execute(
            """
            INSERT OR REPLACE INTO runs (
              run_id, created_at, competition_id, status,
              metric_name, score_raw, score_normalized, local_validation_metric,
              runtime_seconds, budget_time_seconds,
              provider, model_id, mode, temperature, max_tokens,
              submission_path, normalized_submission_path,
              submission_sha256, normalized_submission_sha256,
              spec_sha256, prompt_sha256, public_manifest_sha256, kilo_version, kilo_config_sha256,
              benchmark_version, git_sha, git_dirty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.created_at,
                run.competition_id,
                run.status,
                run.metric_name,
                run.score_raw,
                run.score_normalized,
                run.local_validation_metric,
                run.runtime_seconds,
                run.budget.time_seconds if run.budget else None,
                model.provider if model else None,
                model.model_id if model else None,
                model.mode if model else None,
                model.temperature if model else None,
                model.max_tokens if model else None,
                artifacts.submission_path if artifacts else None,
                artifacts.normalized_submission_path if artifacts else None,
                submission_sha256,
                normalized_submission_sha256,
                spec_sha256,
                prompt_sha256,
                public_manifest_sha256,
                kilo_version,
                kilo_config_sha256,
                versions.benchmark if versions else None,
                versions.git_sha if versions else None,
                _to_int_bool(versions.git_dirty) if versions else None,
            ),
        )
        con.commit()
    finally:
        con.close()


def fetch_runs(db_path: str | Path, *, competition_id: str | None = None) -> list[dict[str, Any]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        if competition_id:
            rows = con.execute("SELECT * FROM runs WHERE competition_id=? ORDER BY created_at DESC", (competition_id,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
