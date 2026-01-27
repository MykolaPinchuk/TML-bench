from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.prepare_lib import prepare_holdout_from_train
from orchestrator.schemas import load_spec


COMPETITION_ID = "foot-traffic-wuerzburg-retail-forecasting-2-0"
ZIP_NAME = f"{COMPETITION_ID}.zip"


def _read_template_readme(base_dir: Path) -> str:
    template_path = base_dir / "public_template" / "README_task.md"
    return template_path.read_text(encoding="utf-8")


def _ensure_raw_files(*, raw_dir: Path, allow_download: bool) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    train_csv = raw_dir / "train.csv"
    test_csv = raw_dir / "test.csv"
    sample_csv = raw_dir / "sample_submission.csv"

    if train_csv.exists() and test_csv.exists() and sample_csv.exists():
        return train_csv

    zip_path = raw_dir / ZIP_NAME
    if not zip_path.exists():
        if not allow_download:
            raise FileNotFoundError(f"Missing raw files under {raw_dir}. Either place {ZIP_NAME} there or run with --download.")
        subprocess.run(
            ["kaggle", "competitions", "download", "-c", COMPETITION_ID, "-p", str(raw_dir), "--force"],
            check=True,
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(raw_dir)

    if not (train_csv.exists() and test_csv.exists() and sample_csv.exists()):
        raise FileNotFoundError(f"Expected train/test/sample CSVs after extracting {zip_path}")
    return train_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, default=str(Path(__file__).with_name("spec.yaml")))
    parser.add_argument("--download", action="store_true", help="Download data via Kaggle CLI into raw/.")
    parser.add_argument("--public-dir", type=str, default=str(Path(__file__).with_name("public")))
    parser.add_argument("--private-dir", type=str, default=str(Path(__file__).with_name("private")))
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    raw_dir = base_dir / "raw"
    spec_path = Path(args.spec)
    spec = load_spec(spec_path)

    train_csv = _ensure_raw_files(raw_dir=raw_dir, allow_download=args.download)

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

