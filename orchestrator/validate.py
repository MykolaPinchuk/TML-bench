from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from orchestrator.schemas import CompetitionSpec


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    errors: list[ValidationError]
    normalized_submission_path: str | None = None


def validate_and_normalize_submission(
    *,
    spec: CompetitionSpec,
    public_dir: str | Path,
    submission_csv: str | Path,
    normalized_out_csv: str | Path | None = None,
) -> ValidationResult:
    public_dir = Path(public_dir)
    submission_csv = Path(submission_csv)
    errors: list[ValidationError] = []

    if not submission_csv.exists():
        return ValidationResult(ok=False, status="invalid_submission", errors=[ValidationError("missing_file", "submission.csv not found")])

    try:
        sample = pd.read_csv(public_dir / "sample_submission.csv")
        test_public = pd.read_csv(public_dir / "test_public.csv")
        sub = pd.read_csv(submission_csv)
    except Exception as e:  # noqa: BLE001
        return ValidationResult(ok=False, status="invalid_submission", errors=[ValidationError("read_error", str(e))])

    expected_cols = list(sample.columns)
    if set(sub.columns) != set(expected_cols):
        errors.append(
            ValidationError(
                "bad_columns",
                f"Expected columns {expected_cols}, got {list(sub.columns)}",
            )
        )
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    if len(sub) != len(test_public):
        errors.append(
            ValidationError(
                "bad_rowcount",
                f"Expected {len(test_public)} rows (test_public), got {len(sub)}",
            )
        )
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    if spec.id_column not in sub.columns:
        errors.append(ValidationError("missing_id_column", f"Missing id column {spec.id_column}"))
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    if sub[spec.id_column].isna().any():
        errors.append(ValidationError("nan_id", "id column contains NaNs"))
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    if sub[spec.id_column].duplicated().any():
        errors.append(ValidationError("duplicate_id", "id column contains duplicates"))
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    test_ids = test_public[spec.id_column]
    sub_ids = sub[spec.id_column]
    if set(sub_ids) != set(test_ids):
        errors.append(ValidationError("id_mismatch", "submission ids do not match test_public ids"))
        return ValidationResult(ok=False, status="invalid_submission", errors=errors)

    pred_cols = [c for c in expected_cols if c != spec.id_column]
    for c in pred_cols:
        coerced = pd.to_numeric(sub[c], errors="coerce")
        if coerced.isna().any():
            errors.append(ValidationError("nan_prediction", f"prediction column {c} contains NaNs/non-numeric"))
            return ValidationResult(ok=False, status="invalid_submission", errors=errors)
        sub[c] = coerced

    sub = sub.set_index(spec.id_column)
    sub = sub.loc[test_ids.values].reset_index()

    out_path = None
    if normalized_out_csv is not None:
        out_path = Path(normalized_out_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sub.to_csv(out_path, index=False)

    return ValidationResult(ok=True, status="success", errors=[], normalized_submission_path=str(out_path) if out_path else None)

