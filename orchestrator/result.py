from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _pacific_tz_name() -> str:
    return "America/Los_Angeles"


def _get_pacific_tz():
    try:
        from zoneinfo import ZoneInfo  # type: ignore

        return ZoneInfo(_pacific_tz_name())
    except Exception:
        return None


def _now_iso() -> str:
    tz = _get_pacific_tz()
    now = datetime.now(tz) if tz is not None else datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat()


def _git_head_sha(repo_root: Path) -> str | None:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
        return out or None
    except Exception:  # noqa: BLE001
        return None


def _is_git_dirty(repo_root: Path) -> bool | None:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True)
        return bool(out.strip())
    except Exception:  # noqa: BLE001
        return None


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model_id: str
    mode: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class BudgetConfig:
    time_seconds: int | None = None


@dataclass(frozen=True)
class Versions:
    benchmark: str
    git_sha: str | None = None
    git_dirty: bool | None = None


@dataclass(frozen=True)
class Artifacts:
    submission_path: str | None = None
    normalized_submission_path: str | None = None
    notes: dict[str, Any] | None = None


@dataclass(frozen=True)
class RunResult:
    run_id: str
    created_at: str
    competition_id: str
    status: str

    score_raw: float | None = None
    score_normalized: float | None = None
    metric_name: str | None = None

    local_validation_metric: float | None = None
    runtime_seconds: float | None = None

    model: ModelConfig | None = None
    budget: BudgetConfig | None = None
    seed: int | None = None

    artifacts: Artifacts | None = None
    versions: Versions | None = None


def new_run_id(*, prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def build_versions(*, repo_root: Path, benchmark_version: str) -> Versions:
    return Versions(benchmark=benchmark_version, git_sha=_git_head_sha(repo_root), git_dirty=_is_git_dirty(repo_root))


def write_result_json(result: RunResult, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True), encoding="utf-8")


def read_result_json(path: str | Path) -> RunResult:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    model_raw = raw.get("model")
    budget_raw = raw.get("budget")
    artifacts_raw = raw.get("artifacts")
    versions_raw = raw.get("versions")

    model = ModelConfig(**model_raw) if isinstance(model_raw, dict) else None
    budget = BudgetConfig(**budget_raw) if isinstance(budget_raw, dict) else None
    artifacts = Artifacts(**artifacts_raw) if isinstance(artifacts_raw, dict) else None
    versions = Versions(**versions_raw) if isinstance(versions_raw, dict) else None

    return RunResult(
        run_id=str(raw["run_id"]),
        created_at=str(raw["created_at"]),
        competition_id=str(raw["competition_id"]),
        status=str(raw["status"]),
        score_raw=raw.get("score_raw"),
        score_normalized=raw.get("score_normalized"),
        metric_name=raw.get("metric_name"),
        local_validation_metric=raw.get("local_validation_metric"),
        runtime_seconds=raw.get("runtime_seconds"),
        model=model,
        budget=budget,
        seed=raw.get("seed"),
        artifacts=artifacts,
        versions=versions,
    )


def default_benchmark_version() -> str:
    return os.environ.get("TML_BENCHMARK_VERSION", "v1-dev")


def make_result(
    *,
    competition_id: str,
    status: str,
    metric_name: str | None,
    score_raw: float | None,
    score_normalized: float | None,
    local_validation_metric: float | None,
    runtime_seconds: float | None,
    budget_time_seconds: int | None,
    model: ModelConfig | None = None,
    submission_path: Path | None,
    normalized_submission_path: Path | None,
    repo_root: Path,
    run_id_prefix: str | None = None,
) -> RunResult:
    run_id = new_run_id(prefix=run_id_prefix or competition_id)
    return RunResult(
        run_id=run_id,
        created_at=_now_iso(),
        competition_id=competition_id,
        status=status,
        metric_name=metric_name,
        score_raw=score_raw,
        score_normalized=score_normalized,
        local_validation_metric=local_validation_metric,
        runtime_seconds=runtime_seconds,
        model=model,
        budget=BudgetConfig(time_seconds=budget_time_seconds) if budget_time_seconds is not None else None,
        artifacts=Artifacts(
            submission_path=str(submission_path) if submission_path else None,
            normalized_submission_path=str(normalized_submission_path) if normalized_submission_path else None,
        ),
        versions=build_versions(repo_root=repo_root, benchmark_version=default_benchmark_version()),
    )
