from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.baseline_sklearn import run_baseline  # noqa: E402
from orchestrator.result import make_result, write_result_json  # noqa: E402
from orchestrator.schemas import load_spec  # noqa: E402
from orchestrator.score import score_submission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition-id", type=str, default="playground-series-s6e1")
    parser.add_argument("--download", action="store_true", help="Download raw data via Kaggle in prepare step.")
    parser.add_argument("--out-dir", type=str, default="tmp/smoke_phase1")
    args = parser.parse_args()

    comp_dir = REPO_ROOT / "competitions" / args.competition_id
    if not comp_dir.exists():
        raise FileNotFoundError(f"competition dir not found: {comp_dir}")

    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    prepare_script = comp_dir / "prepare_competition.py"
    public_dir = comp_dir / "public"
    private_dir = comp_dir / "private"

    cmd = [sys.executable, str(prepare_script)]
    if args.download:
        cmd.append("--download")
    subprocess.run(cmd, check=True)

    submission_out = out_dir / f"{args.competition_id}.submission.csv"
    normalized_out = out_dir / f"{args.competition_id}.submission.normalized.csv"

    baseline = run_baseline(
        competition_dir=comp_dir,
        public_dir=public_dir,
        private_dir=private_dir,
        submission_out=submission_out,
        normalized_out=normalized_out,
    )

    spec = load_spec(comp_dir / "spec.yaml")
    sr = score_submission(spec=spec, private_dir=private_dir, normalized_submission_csv=normalized_out)

    result = make_result(
        competition_id=args.competition_id,
        status="success",
        metric_name=sr.metric_name,
        score_raw=sr.score_raw,
        score_normalized=sr.score_normalized,
        local_validation_metric=baseline.local_validation_metric,
        runtime_seconds=None,
        budget_time_seconds=None,
        submission_path=submission_out,
        normalized_submission_path=normalized_out,
        repo_root=REPO_ROOT,
    )
    result_path = out_dir / f"{result.run_id}.result.json"
    write_result_json(result, result_path)
    print(f"wrote: {result_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
