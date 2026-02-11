from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from orchestrator.db import insert_run
from orchestrator.result import ModelConfig, make_result
from orchestrator.sweep import _derive_prompt_profile, _profile_budget_seconds, _resume_counts_by_model


def _insert_dummy_run(
    *,
    db_path: Path,
    competition_id: str,
    provider: str,
    model_id: str,
    budget_seconds: int,
    prompt_profile: str,
    prompt_strategy: str = "active",
    mode: str | None = None,
    status: str,
) -> None:
    run = make_result(
        competition_id=competition_id,
        status=status,
        metric_name=None,
        score_raw=None,
        score_normalized=None,
        local_validation_metric=None,
        runtime_seconds=1.0,
        budget_time_seconds=budget_seconds,
        model=ModelConfig(provider=provider, model_id=model_id, mode=mode),
        submission_path=None,
        normalized_submission_path=None,
        repo_root=Path("."),
        run_id_prefix=competition_id,
    )
    run = replace(
        run,
        artifacts=replace(
            run.artifacts,
            notes={"prompt_profile": prompt_profile, "prompt_strategy": prompt_strategy},
        ),
    )
    insert_run(db_path, run)


def test_profile_budget_seconds() -> None:
    assert _profile_budget_seconds("simple-baseline") == 240
    assert _profile_budget_seconds("good-baseline") == 600
    assert _profile_budget_seconds("sota-xgb") == 1200


def test_derive_prompt_profile() -> None:
    assert _derive_prompt_profile(budget_seconds=240) == "simple-baseline"
    assert _derive_prompt_profile(budget_seconds=600) == "good-baseline"
    assert _derive_prompt_profile(budget_seconds=1200) == "sota-xgb"
    assert _derive_prompt_profile(budget_seconds=2400) == "sota-xgb"


def test_resume_counts_success_only(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    competition_id = "toy_regression"

    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="chutes",
        model_id="m1",
        budget_seconds=1200,
        prompt_profile="sota-xgb",
        mode=None,
        status="success",
    )
    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="chutes",
        model_id="m1",
        budget_seconds=1200,
        prompt_profile="sota-xgb",
        mode=None,
        status="timeout",
    )
    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="chutes",
        model_id="m1",
        budget_seconds=600,
        prompt_profile="good-baseline",
        mode=None,
        status="success",
    )
    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="chutes",
        model_id="m2",
        budget_seconds=1200,
        prompt_profile="sota-xgb",
        mode=None,
        status="success",
    )

    counts = _resume_counts_by_model(
        db_path=db_path,
        competition_id=competition_id,
        budget_seconds=1200,
        prompt_profile="sota-xgb",
        prompt_strategy="active",
        mode=None,
        any_status=False,
    )
    assert counts[("chutes", "m1")] == 1
    assert counts[("chutes", "m2")] == 1


def test_resume_counts_any_status(tmp_path: Path) -> None:
    db_path = tmp_path / "results.sqlite"
    competition_id = "toy_regression"

    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="nanogpt",
        model_id="m1",
        budget_seconds=240,
        prompt_profile="simple-baseline",
        mode=None,
        status="timeout",
    )
    _insert_dummy_run(
        db_path=db_path,
        competition_id=competition_id,
        provider="nanogpt",
        model_id="m1",
        budget_seconds=240,
        prompt_profile="simple-baseline",
        mode=None,
        status="invalid_submission",
    )

    counts = _resume_counts_by_model(
        db_path=db_path,
        competition_id=competition_id,
        budget_seconds=240,
        prompt_profile="simple-baseline",
        prompt_strategy="active",
        mode=None,
        any_status=True,
    )
    assert counts[("nanogpt", "m1")] == 2
