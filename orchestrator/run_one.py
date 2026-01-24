from __future__ import annotations

import argparse
from dataclasses import replace
import shutil
import sys
from pathlib import Path

from orchestrator.db import insert_run
from orchestrator.leaderboard import LeaderboardPaths, build_leaderboard
from orchestrator.prompting import render_prompt
from orchestrator.result import make_result, write_result_json
from orchestrator.run_state import init_run_state, read_run_state
from orchestrator.run_workspace import copy_public_inputs, create_run_dirs, default_run_id
from orchestrator.schemas import load_spec
from orchestrator.score import score_submission
from orchestrator.validate import validate_and_normalize_submission


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _competition_dir(repo_root: Path, competition_id: str) -> Path:
    return repo_root / "competitions" / competition_id


def cmd_create(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    run_id = args.run_id or default_run_id(competition_id=args.competition_id)
    runs_root = repo_root / "runs"
    paths = create_run_dirs(runs_root=runs_root, run_id=run_id)

    copy_public_inputs(competition_dir=competition_dir, workspace_dir=paths.workspace_dir)
    init_run_state(run_dir=paths.run_dir, time_budget_seconds=spec.budgets.time_seconds)

    prompt = render_prompt(
        base_prompt_path=repo_root / "prompts" / "base_prompt.md",
        override_path=repo_root / "prompts" / "competition_overrides" / f"{args.competition_id}.md",
        time_budget_seconds=spec.budgets.time_seconds,
    )
    paths.instructions_path.write_text(prompt, encoding="utf-8")

    print("Run created.")
    print(f"run_id: {paths.run_id}")
    print(f"workspace: {paths.workspace_dir}")
    print(f"time budget: {spec.budgets.time_seconds} seconds (enforced at finalize)")
    print(f"next: create {paths.workspace_dir/'submission.csv'} (via VSCode/Kilo), then run finalize:")
    print(f"  python -m orchestrator.run_one finalize --competition-id {args.competition_id} --run-id {paths.run_id}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    run_id = args.run_id
    run_dir = repo_root / "runs" / run_id
    workspace_dir = run_dir / "workspace"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state_path = run_dir / "run_state.json"
    if state_path.exists():
        state = read_run_state(state_path)
        runtime_seconds = state.elapsed_seconds()
        budget_seconds = state.time_budget_seconds
    else:
        runtime_seconds = None
        budget_seconds = spec.budgets.time_seconds

    submission_in = workspace_dir / "submission.csv"
    if not submission_in.exists():
        raise FileNotFoundError(f"Missing submission: {submission_in}")

    # Copy submission into artifacts for immutability.
    submission_art = artifacts_dir / "submission.csv"
    shutil.copyfile(submission_in, submission_art)

    normalized_art = artifacts_dir / "submission.normalized.csv"
    vr = validate_and_normalize_submission(
        spec=spec,
        public_dir=competition_dir / "public",
        submission_csv=submission_art,
        normalized_out_csv=normalized_art,
    )

    # Enforce time budget after submission exists (manual Phase 2 timing is coarse but standardized).
    if runtime_seconds is not None and runtime_seconds > float(budget_seconds):
        result = make_result(
            competition_id=args.competition_id,
            status="timeout",
            metric_name=None,
            score_raw=None,
            score_normalized=None,
            local_validation_metric=None,
            runtime_seconds=runtime_seconds,
            budget_time_seconds=budget_seconds,
            submission_path=submission_art,
            normalized_submission_path=None,
            repo_root=repo_root,
            run_id_prefix=args.competition_id,
        )
        result = replace(result, run_id=run_id)
        result_path = run_dir / "result.json"
        write_result_json(result, result_path)
        print(f"timeout: runtime_seconds={runtime_seconds:.1f} > budget_seconds={budget_seconds}; wrote: {result_path}")
        return 3

    if not vr.ok:
        result = make_result(
            competition_id=args.competition_id,
            status="invalid_submission",
            metric_name=None,
            score_raw=None,
            score_normalized=None,
            local_validation_metric=None,
            runtime_seconds=runtime_seconds,
            budget_time_seconds=budget_seconds,
            submission_path=submission_art,
            normalized_submission_path=None,
            repo_root=repo_root,
            run_id_prefix=args.competition_id,
        )
        result_path = run_dir / "result.json"
        write_result_json(result, result_path)
        print(f"invalid submission; wrote: {result_path}")
        for e in vr.errors:
            print(f"- {e.code}: {e.message}")
        return 2

    sr = score_submission(spec=spec, private_dir=competition_dir / "private", normalized_submission_csv=normalized_art)
    result = make_result(
        competition_id=args.competition_id,
        status="success",
        metric_name=sr.metric_name,
        score_raw=sr.score_raw,
        score_normalized=sr.score_normalized,
        local_validation_metric=None,
        runtime_seconds=runtime_seconds,
        budget_time_seconds=budget_seconds,
        submission_path=submission_art,
        normalized_submission_path=normalized_art,
        repo_root=repo_root,
        run_id_prefix=args.competition_id,
    )

    # Overwrite run_id to match directory name.
    result = replace(result, run_id=run_id)

    result_path = run_dir / "result.json"
    write_result_json(result, result_path)
    print(f"wrote: {result_path}")
    print(f"private_holdout_{sr.metric_name}: {sr.score_raw}")
    if runtime_seconds is not None:
        print(f"runtime_seconds: {runtime_seconds:.1f} (budget {budget_seconds}s)")

    if args.db_path:
        db_path = Path(args.db_path)
        insert_run(db_path, result)
        lb_paths = LeaderboardPaths(
            json_path=repo_root / "results" / "leaderboard.json",
            csv_path=repo_root / "results" / "leaderboard.csv",
            html_path=repo_root / "results" / "leaderboard.html",
        )
        build_leaderboard(
            db_path=db_path,
            out_paths=lb_paths,
            competition_id=args.competition_id if args.per_competition else None,
        )
        print(f"updated leaderboard under: {lb_paths.json_path.parent}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a run workspace for a manual VSCode/Kilo agent run.")
    p_create.add_argument("--competition-id", required=True)
    p_create.add_argument("--run-id", default=None)
    p_create.set_defaults(func=cmd_create)

    p_fin = sub.add_parser("finalize", help="Validate + score a run after submission.csv is produced.")
    p_fin.add_argument("--competition-id", required=True)
    p_fin.add_argument("--run-id", required=True)
    p_fin.add_argument("--db-path", default="results/results.sqlite")
    p_fin.add_argument("--per-competition", action="store_true", help="If set, leaderboard is filtered to this competition only.")
    p_fin.set_defaults(func=cmd_finalize)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
