from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from orchestrator.baselines import ensure_competition_baselines
from orchestrator.db import ensure_db
from orchestrator.prepare_lib import prepare_holdout_from_train
from orchestrator.schemas import load_spec


def test_ensure_competition_baselines_records_missing(tmp_path: Path) -> None:
    # Create a tiny synthetic competition directory with spec + prepared public/private.
    comp_dir = tmp_path / "competitions" / "c1"
    comp_dir.mkdir(parents=True)

    spec_src = Path("competitions/toy_regression/spec.yaml")
    spec_dst = comp_dir / "spec.yaml"
    spec_dst.write_text(spec_src.read_text(encoding="utf-8"), encoding="utf-8")
    spec = load_spec(spec_dst)

    raw_train = comp_dir / "raw_train.csv"
    n = 80
    rs = np.random.RandomState(0)
    df = pd.DataFrame({"id": np.arange(n), "x": rs.normal(size=n)})
    df[spec.target_column] = 2.0 * df["x"] + rs.normal(scale=0.1, size=n)
    df.to_csv(raw_train, index=False)

    public_dir = comp_dir / "public"
    private_dir = comp_dir / "private"
    prepare_holdout_from_train(
        spec=spec,
        spec_path=spec_dst,
        raw_train_csv=raw_train,
        public_dir=public_dir,
        private_dir=private_dir,
        readme_task_md="x",
    )

    db_path = tmp_path / "results.sqlite"
    ensure_db(db_path)

    res = ensure_competition_baselines(
        db_path=db_path,
        competition_id="c1",
        competition_dir=comp_dir,
        baseline_types=["constant", "hgb"],
        repo_root=tmp_path,
    )
    assert res["status"] == "ok"
    assert set(res["recorded"]) == {"constant", "hgb"}

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("select baseline_type from baselines where competition_id='c1' order by baseline_type").fetchall()
    finally:
        con.close()
    assert [r[0] for r in rows] == ["constant", "hgb"]

