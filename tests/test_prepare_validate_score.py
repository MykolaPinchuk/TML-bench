from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from orchestrator.prepare_lib import prepare_holdout_from_train
from orchestrator.schemas import load_spec
from orchestrator.score import score_submission
from orchestrator.validate import validate_and_normalize_submission


def test_prepare_is_deterministic(tmp_path: Path) -> None:
    raw_train = tmp_path / "train.csv"
    n = 200
    df = pd.DataFrame(
        {
            "id": np.arange(n),
            "x1": np.random.RandomState(0).normal(size=n),
            "x2": np.random.RandomState(1).normal(size=n),
        }
    )
    df["y"] = 3.0 * df["x1"] - 2.0 * df["x2"] + np.random.RandomState(2).normal(scale=0.1, size=n)
    df.to_csv(raw_train, index=False)

    spec_path = Path("competitions/toy_regression/spec.yaml")
    spec = load_spec(spec_path)

    out1_pub, out1_priv = tmp_path / "out1/public", tmp_path / "out1/private"
    out2_pub, out2_priv = tmp_path / "out2/public", tmp_path / "out2/private"

    prepare_holdout_from_train(
        spec=spec,
        raw_train_csv=raw_train,
        public_dir=out1_pub,
        private_dir=out1_priv,
        readme_task_md="x",
    )
    prepare_holdout_from_train(
        spec=spec,
        raw_train_csv=raw_train,
        public_dir=out2_pub,
        private_dir=out2_priv,
        readme_task_md="x",
    )

    m1 = json.loads((out1_pub / "public_manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2_pub / "public_manifest.json").read_text(encoding="utf-8"))
    assert m1["files"]["train_public.csv"]["sha256"] == m2["files"]["train_public.csv"]["sha256"]
    assert m1["files"]["test_public.csv"]["sha256"] == m2["files"]["test_public.csv"]["sha256"]

    split1 = json.loads((out1_priv / "split.json").read_text(encoding="utf-8"))
    split2 = json.loads((out2_priv / "split.json").read_text(encoding="utf-8"))
    assert split1["split"] == split2["split"]
    assert split1["raw_train"]["sha256"] == split2["raw_train"]["sha256"]
    assert split1["counts"] == split2["counts"]


def test_validate_and_score_roundtrip(tmp_path: Path) -> None:
    raw_train = tmp_path / "train.csv"
    n = 200
    rs = np.random.RandomState(0)
    df = pd.DataFrame({"id": np.arange(n), "x": rs.normal(size=n)})
    df["y"] = 5.0 * df["x"] + rs.normal(scale=0.1, size=n)
    df.to_csv(raw_train, index=False)

    spec = load_spec("competitions/toy_regression/spec.yaml")
    public_dir = tmp_path / "public"
    private_dir = tmp_path / "private"
    prepare_holdout_from_train(spec=spec, raw_train_csv=raw_train, public_dir=public_dir, private_dir=private_dir, readme_task_md="x")

    test_public = pd.read_csv(public_dir / "test_public.csv")
    submission = pd.DataFrame({spec.id_column: test_public[spec.id_column].values, "y": np.zeros(len(test_public))})
    submission_path = tmp_path / "submission.csv"
    submission.to_csv(submission_path, index=False)

    normalized_path = tmp_path / "normalized.csv"
    vr = validate_and_normalize_submission(
        spec=spec, public_dir=public_dir, submission_csv=submission_path, normalized_out_csv=normalized_path
    )
    assert vr.ok

    sr = score_submission(spec=spec, private_dir=private_dir, normalized_submission_csv=normalized_path)
    assert np.isfinite(sr.score_raw)
    assert sr.metric_name == "rmse"

