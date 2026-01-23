from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.baseline_sklearn import run_baseline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition-dir", type=str, required=True)
    parser.add_argument("--public-dir", type=str, default=None)
    parser.add_argument("--private-dir", type=str, default=None)
    parser.add_argument("--out", type=str, default="submission.csv")
    parser.add_argument("--normalized-out", type=str, default=None)
    args = parser.parse_args()

    run_baseline(
        competition_dir=Path(args.competition_dir),
        public_dir=Path(args.public_dir) if args.public_dir else None,
        private_dir=Path(args.private_dir) if args.private_dir else None,
        submission_out=Path(args.out),
        normalized_out=Path(args.normalized_out) if args.normalized_out else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

