from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator.prepare_lib import prepare_holdout_from_train
from orchestrator.schemas import load_spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, default=str(Path(__file__).with_name("spec.yaml")))
    parser.add_argument("--raw-train", type=str, required=True, help="Path to raw train.csv (with labels).")
    parser.add_argument("--public-dir", type=str, required=True, help="Output directory for agent-visible files.")
    parser.add_argument("--private-dir", type=str, required=True, help="Output directory for private holdout labels/meta.")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    prepare_holdout_from_train(
        spec=spec,
        spec_path=Path(args.spec),
        raw_train_csv=Path(args.raw_train),
        public_dir=Path(args.public_dir),
        private_dir=Path(args.private_dir),
        readme_task_md=(
            "# Toy regression task\n\n"
            "Train a regression model on `train_public.csv` to predict `y`.\n\n"
            "Write `submission.csv` with columns `id,y` matching `sample_submission.csv`.\n"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
