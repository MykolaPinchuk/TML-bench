from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.metrics import log_loss, mean_absolute_error, mean_squared_error, roc_auc_score, root_mean_squared_error

from orchestrator.schemas import CompetitionSpec


@dataclass(frozen=True)
class ScoreResult:
    score_raw: float
    score_normalized: float
    metric_name: str


def score_submission(
    *,
    spec: CompetitionSpec,
    private_dir: str | Path,
    normalized_submission_csv: str | Path,
) -> ScoreResult:
    private_dir = Path(private_dir)
    normalized_submission_csv = Path(normalized_submission_csv)

    labels = pd.read_parquet(private_dir / "holdout_labels.parquet")
    sub = pd.read_csv(normalized_submission_csv)

    pred_cols = spec.submission.resolved_prediction_columns()
    expected_cols = [spec.id_column] + pred_cols
    if list(sub.columns) != expected_cols:
        raise ValueError(f"Expected submission columns {expected_cols}, got {list(sub.columns)}")

    merged = labels.merge(sub, on=spec.id_column, how="inner", validate="one_to_one", suffixes=("_label", "_pred"))
    if len(merged) != len(labels):
        raise ValueError("Submission does not cover all holdout labels")

    y_true_col = spec.target_column
    if y_true_col not in merged.columns and f"{y_true_col}_label" in merged.columns:
        y_true_col = f"{y_true_col}_label"
    y_true = merged[y_true_col].to_numpy()

    metric = spec.metric.name
    if metric == "rmse":
        pred_col = pred_cols[0]
        if pred_col not in merged.columns and f"{pred_col}_pred" in merged.columns:
            pred_col = f"{pred_col}_pred"
        y_pred = merged[pred_col].to_numpy()
        try:
            score_raw = float(root_mean_squared_error(y_true, y_pred))
        except Exception:  # noqa: BLE001
            score_raw = float(mean_squared_error(y_true, y_pred) ** 0.5)
    elif metric == "mae":
        pred_col = pred_cols[0]
        if pred_col not in merged.columns and f"{pred_col}_pred" in merged.columns:
            pred_col = f"{pred_col}_pred"
        y_pred = merged[pred_col].to_numpy()
        score_raw = float(mean_absolute_error(y_true, y_pred))
    elif metric == "logloss":
        if spec.task_type == "binary":
            pred_col = pred_cols[0]
            if pred_col not in merged.columns and f"{pred_col}_pred" in merged.columns:
                pred_col = f"{pred_col}_pred"
            y_pred = merged[pred_col].to_numpy()
            score_raw = float(log_loss(y_true, y_pred, labels=[0, 1]))
        else:
            resolved = []
            for c in pred_cols:
                if c in merged.columns:
                    resolved.append(c)
                elif f"{c}_pred" in merged.columns:
                    resolved.append(f"{c}_pred")
                else:
                    raise ValueError(f"Missing prediction column after merge: {c}")
            y_pred = merged[resolved].to_numpy()
            score_raw = float(log_loss(y_true, y_pred))
    elif metric == "auc":
        pred_col = pred_cols[0]
        if pred_col not in merged.columns and f"{pred_col}_pred" in merged.columns:
            pred_col = f"{pred_col}_pred"
        y_pred = merged[pred_col].to_numpy()
        score_raw = float(roc_auc_score(y_true, y_pred))
    else:
        raise ValueError(f"Unsupported metric: {metric}")

    score_normalized = score_raw if spec.metric.higher_is_better else -score_raw
    return ScoreResult(score_raw=score_raw, score_normalized=score_normalized, metric_name=metric)
