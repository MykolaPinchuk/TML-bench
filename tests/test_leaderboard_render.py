from __future__ import annotations

from pathlib import Path

import pandas as pd

from orchestrator.leaderboard import write_root_leaderboard


def test_best_by_model_uses_best_run_score_and_hash(tmp_path: Path) -> None:
    # Two runs for the same model, different scores; leaderboard must pick the best score (lowest rmse).
    df = pd.DataFrame(
        [
            {
                "run_id": "r1",
                "created_at": "2026-01-24T12:00:00-08:00",
                "competition_id": "c1",
                "status": "success",
                "provider": "nanogpt",
                "model_id": "m1",
                "mode": "",
                "metric_name": "rmse",
                "score_raw": 2.0,
                "runtime_seconds": 10.0,
                "budget_time_seconds": 180,
                "submission_sha256": "1" * 16 + "…",
                "normalized_submission_sha256": "a" * 16 + "…",
            },
            {
                "run_id": "r2",
                "created_at": "2026-01-24T12:01:00-08:00",
                "competition_id": "c1",
                "status": "success",
                "provider": "nanogpt",
                "model_id": "m1",
                "mode": "",
                "metric_name": "rmse",
                "score_raw": 1.0,
                "runtime_seconds": 12.0,
                "budget_time_seconds": 180,
                "submission_sha256": "2" * 16 + "…",
                "normalized_submission_sha256": "b" * 16 + "…",
            },
            {
                "run_id": "r3",
                "created_at": "2026-01-24T12:02:00-08:00",
                "competition_id": "c1",
                "status": "success",
                "provider": "chutes",
                "model_id": "m2",
                "mode": "",
                "metric_name": "rmse",
                "score_raw": 1.0,
                "runtime_seconds": 11.0,
                "budget_time_seconds": 180,
                "submission_sha256": "3" * 16 + "…",
                "normalized_submission_sha256": "c" * 16 + "…",
            },
        ]
    )

    # This writes LEADERBOARD.md/html into tmp_path.
    write_root_leaderboard(df=df, repo_root=tmp_path)

    md = (tmp_path / "LEADERBOARD.md").read_text(encoding="utf-8")
    # Best run for (nanogpt, m1) must be r2, not r1.
    assert "| c1 | nanogpt | m1 |" in md
    assert "| c1 | nanogpt | m1 |  | rmse | 1.0 |" in md
    assert "| r2 |" in md
    assert ("2" * 16 + "…") in md
