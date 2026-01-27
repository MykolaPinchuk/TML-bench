from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.prepare_lib import prepare_holdout_from_train
from orchestrator.schemas import (
    BudgetSpec,
    CompetitionSpec,
    MetricSpec,
    PrepareSpec,
    SplitSpec,
    SubmissionSpec,
    load_spec,
)


COMPETITION_ID = "predicting-road-accident-risk-buaa"
ZIP_NAME = f"{COMPETITION_ID}.zip"


def _read_template_readme(base_dir: Path) -> str:
    template_path = base_dir / "public_template" / "README_task.md"
    return template_path.read_text(encoding="utf-8")


def _ensure_raw_files(*, raw_dir: Path, allow_download: bool) -> tuple[Path, Path, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    train_csv = raw_dir / "train.csv"
    test_csv = raw_dir / "test.csv"
    sample_csv = raw_dir / "sample_submission.csv"

    if train_csv.exists() and test_csv.exists() and sample_csv.exists():
        return train_csv, test_csv, sample_csv

    zip_path = raw_dir / ZIP_NAME
    if not zip_path.exists():
        if not allow_download:
            raise FileNotFoundError(
                f"Missing raw files under {raw_dir}. Either place {ZIP_NAME} there or run with --download."
            )
        subprocess.run(
            ["kaggle", "competitions", "download", "-c", COMPETITION_ID, "-p", str(raw_dir), "--force"],
            check=True,
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(raw_dir)

    if not (train_csv.exists() and test_csv.exists() and sample_csv.exists()):
        raise FileNotFoundError(f"Expected train/test/sample CSVs after extracting {zip_path}")
    return train_csv, test_csv, sample_csv


def _read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        row = next(reader, None)
    if not row:
        raise ValueError(f"Empty CSV (no header): {path}")
    return [c.strip() for c in row if str(c).strip()]


def _sample_target_values(*, train_csv: Path, target_column: str, max_rows: int = 2000) -> list[float]:
    vals: list[float] = []
    with train_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or target_column not in set(reader.fieldnames):
            raise ValueError(f"Missing target column {target_column!r} in {train_csv}")
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            raw = (row.get(target_column) or "").strip()
            if raw == "":
                continue
            try:
                vals.append(float(raw))
            except ValueError:
                continue
    return vals


def _infer_spec_from_raw(
    *,
    spec_path: Path,
    train_csv: Path,
    test_csv: Path,
    sample_csv: Path,
) -> CompetitionSpec:
    # Defaults from the checked-in scaffold; overwritten by inference below.
    budgets_time_seconds = 600
    split_test_size = 0.2
    split_seed = 1337

    try:
        base = load_spec(spec_path)
        budgets_time_seconds = int(base.budgets.time_seconds)
        split_test_size = float(base.split.test_size)
        split_seed = int(base.split.seed)
    except Exception:  # noqa: BLE001
        pass

    sample_cols = _read_csv_header(sample_csv)
    if len(sample_cols) < 2:
        raise ValueError(f"Expected >=2 columns in {sample_csv}, got {sample_cols}")
    id_column = sample_cols[0]
    submission_pred_cols = sample_cols[1:]

    train_cols = _read_csv_header(train_csv)
    test_cols = _read_csv_header(test_csv)

    train_set = set(train_cols)
    test_set = set(test_cols)
    train_only = [c for c in train_cols if c not in test_set]
    train_only = [c for c in train_only if c != id_column]

    target_column: str | None = None
    if len(submission_pred_cols) == 1 and submission_pred_cols[0] in train_set:
        target_column = submission_pred_cols[0]
    elif len(train_only) == 1:
        target_column = train_only[0]

    if not target_column:
        raise ValueError(
            "Unable to infer target column.\n"
            f"- sample_submission prediction columns: {submission_pred_cols}\n"
            f"- train-only columns (train minus test, excluding id): {train_only}\n"
            "Fix by editing spec.yaml (target_column/id_column/submission.*) to match the downloaded CSVs."
        )

    # Infer task type / metric from submission shape + a small sample of target values.
    if len(submission_pred_cols) > 1:
        task_type = "multiclass"
        metric_name = "logloss"
        higher_is_better = False
        split_strategy = "stratified"
    else:
        vals = _sample_target_values(train_csv=train_csv, target_column=target_column, max_rows=2000)
        uniq = sorted(set(vals))
        is_binary = len(uniq) <= 2 and all(v in (0.0, 1.0) for v in uniq)
        is_small_int_classes = (
            2 < len(uniq) <= 20 and all(abs(v - round(v)) < 1e-9 for v in uniq) and min(uniq) >= 0 and max(uniq) <= 50
        )

        if is_binary:
            task_type = "binary"
            metric_name = "auc"
            higher_is_better = True
            split_strategy = "stratified"
        elif is_small_int_classes:
            task_type = "multiclass"
            metric_name = "logloss"
            higher_is_better = False
            split_strategy = "stratified"
        else:
            task_type = "regression"
            metric_name = "rmse"
            higher_is_better = False
            split_strategy = "random"

    submission = SubmissionSpec(
        filename="submission.csv",
        prediction_column=submission_pred_cols[0] if len(submission_pred_cols) == 1 else None,
        prediction_columns=submission_pred_cols if len(submission_pred_cols) > 1 else None,
    )

    return CompetitionSpec(
        id=COMPETITION_ID,
        task_type=task_type,  # type: ignore[arg-type]
        target_column=target_column,
        id_column=id_column,
        metric=MetricSpec(name=metric_name, higher_is_better=higher_is_better),  # type: ignore[arg-type]
        submission=submission,
        split=SplitSpec(strategy=split_strategy, test_size=split_test_size, seed=split_seed),  # type: ignore[arg-type]
        budgets=BudgetSpec(time_seconds=budgets_time_seconds),
        prepare=PrepareSpec(raw_train_path="raw/train.csv"),
    )


def _spec_to_yaml_text(spec: CompetitionSpec) -> str:
    preds = spec.submission.resolved_prediction_columns()
    if len(preds) == 1:
        pred_block = f"  prediction_column: {preds[0]}\n"
    else:
        pred_block = "  prediction_columns:\n" + "".join(f"    - {c}\n" for c in preds)

    return (
        f"id: {spec.id}\n"
        f"task_type: {spec.task_type}\n\n"
        f"target_column: {spec.target_column}\n"
        f"id_column: {spec.id_column}\n\n"
        "metric:\n"
        f"  name: {spec.metric.name}\n"
        f"  higher_is_better: {'true' if spec.metric.higher_is_better else 'false'}\n\n"
        "submission:\n"
        f"  filename: {spec.submission.filename}\n"
        f"{pred_block}\n"
        "split:\n"
        f"  strategy: {spec.split.strategy}\n"
        f"  test_size: {spec.split.test_size}\n"
        f"  seed: {spec.split.seed}\n\n"
        "budgets:\n"
        f"  time_seconds: {spec.budgets.time_seconds}\n\n"
        "prepare:\n"
        f"  raw_train_path: {spec.prepare.raw_train_path}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, default=str(Path(__file__).with_name("spec.yaml")))
    parser.add_argument("--download", action="store_true", help="Download data via Kaggle CLI into raw/.")
    parser.add_argument("--write-spec", action="store_true", help="Rewrite spec.yaml inferred from downloaded data.")
    parser.add_argument("--public-dir", type=str, default=str(Path(__file__).with_name("public")))
    parser.add_argument("--private-dir", type=str, default=str(Path(__file__).with_name("private")))
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "raw"
    spec_path = Path(args.spec)

    train_csv, test_csv, sample_csv = _ensure_raw_files(raw_dir=raw_dir, allow_download=args.download)

    inferred = _infer_spec_from_raw(spec_path=spec_path, train_csv=train_csv, test_csv=test_csv, sample_csv=sample_csv)

    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
    should_write = args.write_spec or ("__INFER__" in spec_text)
    if should_write:
        spec_path.write_text(_spec_to_yaml_text(inferred), encoding="utf-8")
        spec = inferred
    else:
        spec = load_spec(spec_path)
        # Ensure the checked-in spec still matches the downloaded data.
        if (
            spec.id_column != inferred.id_column
            or spec.target_column != inferred.target_column
            or spec.task_type != inferred.task_type
            or spec.metric.name != inferred.metric.name
            or spec.submission.resolved_prediction_columns() != inferred.submission.resolved_prediction_columns()
        ):
            raise ValueError(
                "spec.yaml does not match downloaded data. Re-run with --write-spec to refresh:\n"
                f"  KAGGLE_CONFIG_DIR=secrets python {Path(__file__).relative_to(REPO_ROOT)} --download --write-spec\n"
            )

    public_dir = Path(args.public_dir)
    private_dir = Path(args.private_dir)
    if public_dir.exists():
        shutil.rmtree(public_dir)
    if private_dir.exists():
        shutil.rmtree(private_dir)

    prepare_holdout_from_train(
        spec=spec,
        spec_path=spec_path,
        raw_train_csv=train_csv,
        public_dir=public_dir,
        private_dir=private_dir,
        readme_task_md=_read_template_readme(base_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

