from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

from orchestrator.hash_utils import sha256_file
from orchestrator.schemas import CompetitionSpec


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_manifest(public_dir: Path, *, spec_hash: str, competition_id: str) -> None:
    files: dict[str, Any] = {}
    for name in ["train_public.csv", "test_public.csv", "sample_submission.csv", "README_task.md"]:
        p = public_dir / name
        if not p.exists():
            continue
        entry: dict[str, Any] = {"sha256": sha256_file(p)}
        if p.suffix == ".csv":
            df = pd.read_csv(p)
            entry["rows"] = int(df.shape[0])
            entry["cols"] = int(df.shape[1])
        files[name] = entry

    manifest = {
        "competition_id": competition_id,
        "created_at": _utc_iso(),
        "spec_hash": f"sha256:{spec_hash}",
        "files": files,
    }
    (public_dir / "public_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def prepare_holdout_from_train(
    *,
    spec: CompetitionSpec,
    spec_path: Path | None = None,
    raw_train_csv: Path,
    public_dir: Path,
    private_dir: Path,
    readme_task_md: str,
) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(raw_train_csv)
    if spec.target_column not in train.columns:
        raise ValueError(f"Missing target column in raw train: {spec.target_column}")
    if spec.id_column not in train.columns:
        train.insert(0, spec.id_column, range(len(train)))

    train_ids = train[spec.id_column]
    if train_ids.isna().any():
        raise ValueError("id_column contains NaNs in raw train")
    if train_ids.duplicated().any():
        raise ValueError("id_column contains duplicates in raw train")

    features = train.drop(columns=[spec.target_column])
    y = train[spec.target_column]

    stratify = None
    if spec.split.strategy == "stratified":
        stratify = y
    elif spec.split.strategy in ("group", "time"):
        raise NotImplementedError(f"split.strategy={spec.split.strategy} not implemented yet")

    X_train, X_holdout, y_train, y_holdout = train_test_split(
        features,
        y,
        test_size=spec.split.test_size,
        random_state=spec.split.seed,
        stratify=stratify,
    )

    train_public = X_train.copy()
    train_public[spec.target_column] = y_train

    test_public = X_holdout.copy()
    holdout_labels = pd.DataFrame({spec.id_column: X_holdout[spec.id_column].values, spec.target_column: y_holdout.values})

    train_public.to_csv(public_dir / "train_public.csv", index=False)
    test_public.to_csv(public_dir / "test_public.csv", index=False)

    pred_cols = spec.submission.resolved_prediction_columns()
    sample = pd.DataFrame({spec.id_column: test_public[spec.id_column].values})
    for c in pred_cols:
        sample[c] = 0.0
    sample.to_csv(public_dir / "sample_submission.csv", index=False)

    (public_dir / "README_task.md").write_text(readme_task_md.strip() + "\n", encoding="utf-8")

    holdout_labels.to_parquet(private_dir / "holdout_labels.parquet", index=False)

    split_mapping = pd.DataFrame(
        {
            spec.id_column: pd.concat([train_public[spec.id_column], test_public[spec.id_column]], ignore_index=True),
            "split": (["train_public"] * len(train_public)) + (["holdout"] * len(test_public)),
        }
    ).sort_values(spec.id_column)
    split_mapping_path = private_dir / "split_mapping.csv"
    split_mapping.to_csv(split_mapping_path, index=False)

    split_meta = {
        "competition_id": spec.id,
        "created_at": _utc_iso(),
        "split": asdict(spec.split),
        "raw_train": {"path": str(raw_train_csv), "sha256": sha256_file(raw_train_csv)},
        "split_mapping": {"path": str(split_mapping_path), "sha256": sha256_file(split_mapping_path)},
        "counts": {"train_public_rows": int(train_public.shape[0]), "holdout_rows": int(test_public.shape[0])},
    }
    (private_dir / "split.json").write_text(json.dumps(split_meta, indent=2, sort_keys=True), encoding="utf-8")

    spec_hash = sha256_file(spec_path) if spec_path is not None else "unknown"
    _write_manifest(public_dir, spec_hash=spec_hash, competition_id=spec.id)
