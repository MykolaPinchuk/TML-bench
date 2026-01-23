from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


TaskType = Literal["regression", "binary", "multiclass"]
SplitStrategy = Literal["random", "stratified", "group", "time"]


@dataclass(frozen=True)
class MetricSpec:
    name: Literal["rmse", "mae", "logloss", "auc"]
    higher_is_better: bool


@dataclass(frozen=True)
class SubmissionSpec:
    filename: str
    prediction_column: str | None = None
    prediction_columns: list[str] | None = None

    def resolved_prediction_columns(self) -> list[str]:
        if self.prediction_columns is not None:
            return list(self.prediction_columns)
        if self.prediction_column is not None:
            return [self.prediction_column]
        raise ValueError("submission must define prediction_column or prediction_columns")


@dataclass(frozen=True)
class SplitSpec:
    strategy: SplitStrategy
    test_size: float
    seed: int
    group_column: str | None = None
    time_column: str | None = None


@dataclass(frozen=True)
class BudgetSpec:
    time_seconds: int


@dataclass(frozen=True)
class PrepareSpec:
    raw_train_path: str


@dataclass(frozen=True)
class CompetitionSpec:
    id: str
    task_type: TaskType
    target_column: str
    id_column: str
    metric: MetricSpec
    submission: SubmissionSpec
    split: SplitSpec
    budgets: BudgetSpec
    prepare: PrepareSpec


def _require(d: dict[str, Any], key: str, typ: type, *, ctx: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required field {ctx}.{key}")
    val = d[key]
    if not isinstance(val, typ):
        raise ValueError(f"Expected {ctx}.{key} to be {typ.__name__}, got {type(val).__name__}")
    return val


def load_spec(path: str | Path) -> CompetitionSpec:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("spec.yaml must be a mapping")

    metric_raw = _require(raw, "metric", dict, ctx="spec")
    submission_raw = _require(raw, "submission", dict, ctx="spec")
    split_raw = _require(raw, "split", dict, ctx="spec")
    budgets_raw = _require(raw, "budgets", dict, ctx="spec")
    prepare_raw = _require(raw, "prepare", dict, ctx="spec")

    metric = MetricSpec(
        name=_require(metric_raw, "name", str, ctx="metric"),
        higher_is_better=bool(metric_raw.get("higher_is_better", False)),
    )

    submission = SubmissionSpec(
        filename=_require(submission_raw, "filename", str, ctx="submission"),
        prediction_column=submission_raw.get("prediction_column"),
        prediction_columns=submission_raw.get("prediction_columns"),
    )

    split = SplitSpec(
        strategy=_require(split_raw, "strategy", str, ctx="split"),
        test_size=float(_require(split_raw, "test_size", (int, float), ctx="split")),
        seed=int(_require(split_raw, "seed", (int, float), ctx="split")),
        group_column=split_raw.get("group_column"),
        time_column=split_raw.get("time_column"),
    )

    budgets = BudgetSpec(time_seconds=int(_require(budgets_raw, "time_seconds", (int, float), ctx="budgets")))
    prepare = PrepareSpec(raw_train_path=_require(prepare_raw, "raw_train_path", str, ctx="prepare"))

    spec = CompetitionSpec(
        id=_require(raw, "id", str, ctx="spec"),
        task_type=_require(raw, "task_type", str, ctx="spec"),
        target_column=_require(raw, "target_column", str, ctx="spec"),
        id_column=_require(raw, "id_column", str, ctx="spec"),
        metric=metric,
        submission=submission,
        split=split,
        budgets=budgets,
        prepare=prepare,
    )

    if spec.task_type not in ("regression", "binary", "multiclass"):
        raise ValueError(f"Invalid task_type: {spec.task_type}")
    if spec.split.strategy not in ("random", "stratified", "group", "time"):
        raise ValueError(f"Invalid split.strategy: {spec.split.strategy}")
    if not (0.0 < spec.split.test_size < 1.0):
        raise ValueError("split.test_size must be between 0 and 1")

    return spec

