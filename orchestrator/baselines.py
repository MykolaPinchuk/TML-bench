from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.baseline_sklearn import run_baseline
from orchestrator.db import fetch_baselines, insert_baseline
from orchestrator.hash_utils import sha256_file
from orchestrator.schemas import load_spec


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_public_manifest_sha(public_dir: Path) -> str | None:
    p = public_dir / "public_manifest.json"
    if not p.exists():
        return None
    try:
        return sha256_file(p)
    except Exception:  # noqa: BLE001
        return None


def _ensure_dirs_exist(*, competition_dir: Path) -> tuple[Path, Path]:
    public_dir = competition_dir / "public"
    private_dir = competition_dir / "private"
    if not public_dir.exists():
        raise FileNotFoundError(f"Missing competition public dir: {public_dir}. Run prepare_competition.py first.")
    if not private_dir.exists():
        raise FileNotFoundError(f"Missing competition private dir: {private_dir}. Run prepare_competition.py first.")
    return public_dir, private_dir


def _baseline_out_dir(*, repo_root: Path, competition_id: str, baseline_type: str) -> Path:
    return repo_root / "tmp" / "baselines" / competition_id / baseline_type


def ensure_competition_baselines(
    *,
    db_path: str | Path,
    competition_id: str,
    competition_dir: Path,
    baseline_types: list[str] | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    baseline_types = baseline_types or ["hgb", "constant"]
    baseline_types = [str(x).strip().lower() for x in baseline_types if str(x).strip()]
    for t in baseline_types:
        if t not in {"hgb", "constant"}:
            raise ValueError(f"Invalid baseline type: {t}")

    try:
        existing = fetch_baselines(db_path)
    except Exception:  # noqa: BLE001
        existing = []
    have = {(str(r.get("competition_id")), str(r.get("baseline_type"))) for r in existing if isinstance(r, dict)}
    missing = [t for t in baseline_types if (competition_id, t) not in have]
    if not missing:
        return {"competition_id": competition_id, "status": "ok", "missing": [], "recorded": []}

    repo_root = repo_root or _repo_root()
    public_dir, private_dir = _ensure_dirs_exist(competition_dir=competition_dir)

    spec_path = competition_dir / "spec.yaml"
    spec = load_spec(spec_path)
    spec_sha = sha256_file(spec_path) if spec_path.exists() else None
    public_manifest_sha = _read_public_manifest_sha(public_dir)
    created_at = _now_utc_iso()

    recorded: list[str] = []
    for baseline_type in missing:
        out_dir = _baseline_out_dir(repo_root=repo_root, competition_id=competition_id, baseline_type=baseline_type)
        out_dir.mkdir(parents=True, exist_ok=True)
        submission_out = out_dir / "submission.csv"
        normalized_out = out_dir / "submission.normalized.csv"

        outputs = run_baseline(
            competition_dir=competition_dir,
            public_dir=public_dir,
            private_dir=private_dir,
            submission_out=submission_out,
            normalized_out=normalized_out,
            baseline_type=baseline_type,
        )

        insert_baseline(
            db_path,
            competition_id=competition_id,
            baseline_type=baseline_type,
            created_at=created_at,
            metric_name=outputs.metric_name or spec.metric.name,
            score_raw=outputs.private_holdout_score_raw,
            score_normalized=outputs.private_holdout_score_normalized,
            local_validation_metric=outputs.local_validation_metric,
            submission_sha256=outputs.submission_sha256,
            normalized_submission_sha256=outputs.normalized_submission_sha256,
            spec_sha256=spec_sha,
            public_manifest_sha256=public_manifest_sha,
        )
        recorded.append(baseline_type)

    return {"competition_id": competition_id, "status": "ok", "missing": missing, "recorded": recorded}


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute and record host baselines (hgb/constant) into results/results.sqlite.")
    ap.add_argument("--competition-id", required=True)
    ap.add_argument("--db-path", default=str(_repo_root() / "results" / "results.sqlite"))
    ap.add_argument(
        "--baseline-types",
        default="hgb,constant",
        help="Comma-separated list from {hgb,constant}. Default: hgb,constant",
    )
    args = ap.parse_args()

    repo_root = _repo_root()
    competition_dir = repo_root / "competitions" / args.competition_id
    baseline_types = [x.strip().lower() for x in str(args.baseline_types).split(",") if x.strip()]
    if not baseline_types:
        raise ValueError("No baseline types selected.")
    for t in baseline_types:
        if t not in {"hgb", "constant"}:
            raise ValueError(f"Invalid baseline type: {t}")

    res = ensure_competition_baselines(
        db_path=args.db_path,
        competition_id=args.competition_id,
        competition_dir=competition_dir,
        baseline_types=baseline_types,
        repo_root=repo_root,
    )
    print(json.dumps({"created_at": _now_utc_iso(), "result": res}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
