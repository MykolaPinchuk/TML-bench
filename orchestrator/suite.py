from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from orchestrator.leaderboard import LeaderboardPaths, build_leaderboard, load_baselines_df, write_root_leaderboard


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_suite(path: Path) -> tuple[str, list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    name = str(raw.get("name") or path.stem).strip()
    comps = raw.get("competitions")
    if not isinstance(comps, list) or not comps:
        raise ValueError(f"Invalid suite file (missing competitions list): {path}")
    competition_ids: list[str] = []
    for i, c in enumerate(comps):
        if not isinstance(c, str) or not c.strip():
            raise ValueError(f"Invalid competition id at index {i} in {path}")
        competition_ids.append(c.strip())
    return name, competition_ids


def _refresh_root_leaderboard(*, repo_root: Path, db_path: Path) -> None:
    lb_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard.json",
        csv_path=repo_root / "results" / "leaderboard.csv",
        html_path=repo_root / "results" / "leaderboard.html",
    )
    df = build_leaderboard(db_path=db_path, out_paths=lb_paths, competition_id=None)
    baselines_df = load_baselines_df(db_path=db_path)
    write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 5: run a sweep across a fixed suite of competitions.")
    ap.add_argument(
        "--suite-path",
        default=str(_repo_root() / "orchestrator" / "suites" / "v5_core.json"),
        help="Path to a JSON suite file listing competitions to run.",
    )
    ap.add_argument(
        "--models-path",
        default=str(_repo_root() / "orchestrator" / "model_sets" / "v3_fast.json"),
        help="JSON file with provider/model_id entries.",
    )
    ap.add_argument(
        "--profile",
        default="simple-baseline",
        choices=["simple-baseline", "good-baseline", "sota-xgb"],
        help="Sweep profile to use for each competition (controls budget + prompt profile).",
    )
    ap.add_argument("--runs-per-model", type=int, default=1)
    ap.add_argument("--db-path", default=str(_repo_root() / "results" / "results.sqlite"))
    ap.add_argument("--concurrency", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--resume-any-status", action="store_true")
    ap.add_argument("--max-models", type=int, default=None)
    ap.add_argument("--max-runs", type=int, default=None, help="If set, applies per-competition.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo_root = _repo_root()
    suite_path = Path(args.suite_path)
    suite_name, competition_ids = _load_suite(suite_path)

    missing_public: list[str] = []
    for cid in competition_ids:
        public_dir = repo_root / "competitions" / cid / "public"
        if not public_dir.exists():
            missing_public.append(cid)
    if missing_public:
        joined = ", ".join(missing_public)
        raise FileNotFoundError(
            "Missing prepared competition public dirs for: "
            f"{joined}. Run each competition's prepare_competition.py first."
        )

    db_path = Path(args.db_path)

    print(f"suite: {suite_name} ({suite_path})")
    print(f"competitions: {len(competition_ids)}")
    print(f"models_path: {args.models_path}")
    print(f"profile: {args.profile} (runs_per_model={args.runs_per_model})")

    rc_total = 0
    for i, cid in enumerate(competition_ids, start=1):
        cmd = [
            sys.executable,
            "-m",
            "orchestrator.sweep",
            "--competition-id",
            cid,
            "--models-path",
            str(args.models_path),
            "--profile",
            str(args.profile),
            "--runs-per-model",
            str(int(args.runs_per_model)),
            "--db-path",
            str(db_path),
        ]
        if args.concurrency is not None:
            cmd += ["--concurrency", str(int(args.concurrency))]
        if args.max_models is not None:
            cmd += ["--max-models", str(int(args.max_models))]
        if args.max_runs is not None:
            cmd += ["--max-runs", str(int(args.max_runs))]
        if args.resume:
            cmd += ["--resume"]
        if args.resume_any_status:
            cmd += ["--resume-any-status"]
        if args.dry_run:
            cmd += ["--dry-run"]

        print(f"\n=== [{i}/{len(competition_ids)}] sweep: {cid} ===")
        if args.dry_run:
            print(" ".join(cmd))
            continue

        proc = subprocess.run(cmd, cwd=repo_root)
        if proc.returncode != 0:
            rc_total = proc.returncode if rc_total == 0 else rc_total

    if not args.dry_run:
        _refresh_root_leaderboard(repo_root=repo_root, db_path=db_path)
        print(f"\nupdated root leaderboard: {repo_root / 'LEADERBOARD.md'}")
        print(f"updated results leaderboard: {repo_root / 'results' / 'leaderboard.json'}")

    return int(rc_total)


if __name__ == "__main__":
    raise SystemExit(main())

