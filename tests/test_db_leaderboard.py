from __future__ import annotations

from pathlib import Path

from orchestrator.db import insert_run
from orchestrator.leaderboard import LeaderboardPaths, build_leaderboard
from orchestrator.result import make_result


def test_insert_and_leaderboard(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    out_paths = LeaderboardPaths(
        json_path=tmp_path / "leaderboard.json",
        csv_path=tmp_path / "leaderboard.csv",
        html_path=tmp_path / "leaderboard.html",
    )

    run = make_result(
        competition_id="toy_regression",
        status="success",
        metric_name="rmse",
        score_raw=1.23,
        score_normalized=-1.23,
        local_validation_metric=2.34,
        runtime_seconds=12.0,
        budget_time_seconds=600,
        submission_path=tmp_path / "submission.csv",
        normalized_submission_path=tmp_path / "submission.normalized.csv",
        repo_root=Path("."),
        run_id_prefix="toy_regression",
    )
    insert_run(db_path, run)

    df = build_leaderboard(db_path=db_path, out_paths=out_paths, competition_id="toy_regression")
    assert len(df) == 1
    assert df.iloc[0]["competition_id"] == "toy_regression"
    assert float(df.iloc[0]["score_raw"]) == 1.23
