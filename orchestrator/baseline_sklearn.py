from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from orchestrator.schemas import CompetitionSpec, load_spec
from orchestrator.score import score_submission
from orchestrator.validate import validate_and_normalize_submission


@dataclass(frozen=True)
class BaselineOutputs:
    submission_path: Path
    normalized_submission_path: Path | None
    local_validation_metric: float | None
    private_holdout_score_raw: float | None


def _build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    categorical_cols = [c for c in X.columns if X[c].dtype == "object" or str(X[c].dtype).startswith("category")]
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_cols),
            ("cat", categorical_pipe, categorical_cols),
        ],
        remainder="drop",
    )


def _constant_predict_regression(*, spec: CompetitionSpec, train_public: pd.DataFrame, test_public: pd.DataFrame) -> tuple[np.ndarray, float | None]:
    y = train_public[spec.target_column].to_numpy()
    const = float(np.mean(y))
    return np.full(shape=(len(test_public),), fill_value=const, dtype=float), None


def _constant_predict_classification(
    *, spec: CompetitionSpec, train_public: pd.DataFrame, test_public: pd.DataFrame
) -> tuple[np.ndarray, float | None]:
    y = train_public[spec.target_column].to_numpy()
    classes, counts = np.unique(y, return_counts=True)
    priors = counts / max(1, counts.sum())
    # For binary, return probability of positive class (assume label 1 if present; else use the higher class).
    if spec.task_type == "binary":
        if 1 in classes:
            p1 = float(priors[list(classes).index(1)])
        else:
            p1 = float(priors[int(np.argmax(classes))])
        return np.full(shape=(len(test_public),), fill_value=p1, dtype=float), None
    # Multiclass: return probabilities per class in the submission column order.
    proba = np.tile(priors.astype(float), (len(test_public), 1))
    return proba, None


def _fit_predict_regression(*, spec: CompetitionSpec, train_public: pd.DataFrame, test_public: pd.DataFrame) -> tuple[np.ndarray, float | None]:
    X = train_public.drop(columns=[spec.target_column])
    y = train_public[spec.target_column].to_numpy()

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=spec.split.seed,
    )

    pre = _build_preprocessor(X_train)
    model = HistGradientBoostingRegressor(random_state=spec.split.seed)
    pipe = Pipeline([("pre", pre), ("model", model)])
    pipe.fit(X_train, y_train)

    pred_val = pipe.predict(X_val)
    metric_name = spec.metric.name
    if metric_name == "rmse":
        rmse = float(np.sqrt(np.mean((pred_val - y_val) ** 2)))
        local_metric = rmse
    elif metric_name == "mae":
        local_metric = float(mean_absolute_error(y_val, pred_val))
    else:
        local_metric = None

    pred_test = pipe.predict(test_public)
    return pred_test, local_metric


def _fit_predict_classification(
    *, spec: CompetitionSpec, train_public: pd.DataFrame, test_public: pd.DataFrame
) -> tuple[np.ndarray, float | None]:
    X = train_public.drop(columns=[spec.target_column])
    y = train_public[spec.target_column].to_numpy()

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=spec.split.seed,
        stratify=y if spec.split.strategy == "stratified" else None,
    )

    pre = _build_preprocessor(X_train)
    model = HistGradientBoostingClassifier(random_state=spec.split.seed)
    pipe = Pipeline([("pre", pre), ("model", model)])
    pipe.fit(X_train, y_train)

    proba_val = pipe.predict_proba(X_val)
    local_metric = None
    if spec.metric.name == "logloss":
        local_metric = float(log_loss(y_val, proba_val))

    proba_test = pipe.predict_proba(test_public)
    if spec.task_type == "binary":
        return proba_test[:, 1], local_metric
    return proba_test, local_metric


def run_baseline(
    *,
    competition_dir: Path,
    public_dir: Path | None,
    private_dir: Path | None,
    submission_out: Path,
    normalized_out: Path | None,
    baseline_type: str = "hgb",
) -> BaselineOutputs:
    spec_path = competition_dir / "spec.yaml"
    spec = load_spec(spec_path)

    public_dir = public_dir or (competition_dir / "public")
    private_dir = private_dir or (competition_dir / "private")

    train_public = pd.read_csv(public_dir / "train_public.csv")
    test_public = pd.read_csv(public_dir / "test_public.csv")

    pred_cols = spec.submission.resolved_prediction_columns()
    if len(pred_cols) != 1 and spec.task_type == "regression":
        raise ValueError("Baseline currently supports single-column regression predictions only")

    baseline_type = str(baseline_type or "").strip().lower()
    if baseline_type not in {"hgb", "constant"}:
        raise ValueError(f"Unsupported baseline_type={baseline_type!r}; expected 'hgb' or 'constant'")

    if baseline_type == "constant":
        if spec.task_type == "regression":
            preds, local_metric = _constant_predict_regression(spec=spec, train_public=train_public, test_public=test_public)
        else:
            preds, local_metric = _constant_predict_classification(spec=spec, train_public=train_public, test_public=test_public)
    else:
        if spec.task_type == "regression":
            preds, local_metric = _fit_predict_regression(spec=spec, train_public=train_public, test_public=test_public)
        else:
            preds, local_metric = _fit_predict_classification(spec=spec, train_public=train_public, test_public=test_public)

    submission = pd.DataFrame({spec.id_column: test_public[spec.id_column].values})
    if spec.task_type == "multiclass":
        if not isinstance(preds, np.ndarray) or preds.ndim != 2:
            raise ValueError("Expected multiclass predictions to be 2D array")
        if len(pred_cols) != preds.shape[1]:
            raise ValueError("submission.prediction_columns must match number of classes for multiclass baseline")
        for i, c in enumerate(pred_cols):
            submission[c] = preds[:, i]
    else:
        submission[pred_cols[0]] = preds

    submission_out.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(submission_out, index=False)

    if normalized_out is None:
        normalized_out = submission_out.with_name(submission_out.stem + ".normalized.csv")

    vr = validate_and_normalize_submission(
        spec=spec,
        public_dir=public_dir,
        submission_csv=submission_out,
        normalized_out_csv=normalized_out,
    )
    if not vr.ok:
        raise ValueError(f"Baseline produced invalid submission: {vr.errors}")

    private_score = None
    if private_dir.exists():
        sr = score_submission(spec=spec, private_dir=private_dir, normalized_submission_csv=normalized_out)
        private_score = sr.score_raw
        if sr.secondary_metrics and "r2" in sr.secondary_metrics:
            print(f"private_holdout_r2: {sr.secondary_metrics['r2']}")

    print(f"wrote: {submission_out}")
    if local_metric is not None:
        print(f"local_valid_{spec.metric.name}: {local_metric}")
    if private_score is not None:
        print(f"private_holdout_{spec.metric.name}: {private_score}")
    print(f"baseline_type: {baseline_type}")

    return BaselineOutputs(
        submission_path=submission_out,
        normalized_submission_path=normalized_out,
        local_validation_metric=local_metric,
        private_holdout_score_raw=private_score,
    )
