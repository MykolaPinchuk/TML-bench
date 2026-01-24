from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from orchestrator.db import fetch_runs


@dataclass(frozen=True)
class LeaderboardPaths:
    json_path: Path
    csv_path: Path
    html_path: Path


def build_leaderboard(
    *,
    db_path: Path,
    out_paths: LeaderboardPaths,
    competition_id: str | None = None,
) -> pd.DataFrame:
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
        "metric_name",
        "score_raw",
        "runtime_seconds",
        "budget_time_seconds",
    ]
    if df_full.empty:
        df = pd.DataFrame(columns=keep)
    else:
        df = df_full[[c for c in keep if c in df_full.columns]].copy()
    # For Phase 2 we keep it simple: show all runs sorted by (competition_id, score_raw) where available.
    df["score_raw"] = pd.to_numeric(df.get("score_raw"), errors="coerce")
    df = df.sort_values(by=["competition_id", "score_raw", "created_at"], ascending=[True, True, False], na_position="last")

    out_paths.json_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.csv_path.parent.mkdir(parents=True, exist_ok=True)
    out_paths.html_path.parent.mkdir(parents=True, exist_ok=True)

    out_paths.json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    df.to_csv(out_paths.csv_path, index=False, quoting=csv.QUOTE_MINIMAL)

    html = df.to_html(index=False, escape=True)
    out_paths.html_path.write_text(html, encoding="utf-8")

    return df
