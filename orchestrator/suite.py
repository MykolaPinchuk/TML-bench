from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from orchestrator.leaderboard import (
    LeaderboardPaths,
    build_leaderboard,
    load_baselines_df,
    write_root_leaderboard,
    write_root_leaderboard_robust,
)
from orchestrator.preflight import preflight_one


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


def _load_model_set(path: Path) -> tuple[dict, list[dict]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    models = raw.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError(f"Invalid model set file (missing models list): {path}")
    out: list[dict] = []
    for i, m in enumerate(models):
        if not isinstance(m, dict):
            raise TypeError(f"Invalid model entry at index {i} in {path}: expected object")
        provider = m.get("provider")
        model_id = m.get("model_id")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(f"Invalid model entry at index {i} in {path}: missing provider")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"Invalid model entry at index {i} in {path}: missing model_id")
        out.append(
            {
                "provider": provider.strip(),
                "model_id": model_id.strip(),
                "label": str(m.get("label") or ""),
            }
        )
    return raw, out


def _write_model_set(*, dst_path: Path, raw: dict, models: list[dict]) -> None:
    obj = dict(raw)
    obj["models"] = models
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _refresh_root_leaderboard(*, repo_root: Path, db_path: Path) -> None:
    lb_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard.json",
        csv_path=repo_root / "results" / "leaderboard.csv",
        html_path=repo_root / "results" / "leaderboard.html",
    )
    df = build_leaderboard(db_path=db_path, out_paths=lb_paths, competition_id=None)
    baselines_df = load_baselines_df(db_path=db_path)
    write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)
    write_root_leaderboard_robust(df=df, repo_root=repo_root, baselines=baselines_df)


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
        "--preflight",
        action="store_true",
        help="If set, do a quick per-model tool-call preflight and skip models that fail.",
    )
    ap.add_argument(
        "--preflight-timeout-seconds",
        type=int,
        default=90,
        help="Timeout for each preflight attempt (seconds).",
    )
    ap.add_argument(
        "--preflight-fail-fast",
        action="store_true",
        help="If set with --preflight, exit non-zero if any model fails preflight.",
    )
    ap.add_argument(
        "--profile",
        default="simple-baseline",
        choices=["simple-baseline", "good-baseline", "sota-xgb"],
        help="Sweep profile to use for each competition (controls budget + prompt profile).",
    )
    ap.add_argument(
        "--budget-seconds",
        type=int,
        default=None,
        help="Optional override for the run time budget passed to orchestrator.sweep (useful for time-only experiments).",
    )
    ap.add_argument(
        "--prompt-profile",
        default=None,
        help="Optional prompt profile id passed to orchestrator.sweep (file in `prompts/prompt_profiles/<id>.md`).",
    )
    ap.add_argument(
        "--prompt-strategy",
        default="active",
        help="Prompt strategy id passed to orchestrator.sweep (`active` uses `prompts/`; otherwise `prompts/strategies/<id>/`).",
    )
    ap.add_argument("--runs-per-model", type=int, default=1)
    ap.add_argument("--db-path", default=str(_repo_root() / "results" / "results.sqlite"))
    ap.add_argument("--concurrency", type=int, default=None)
    ap.add_argument("--mode", default=None, help="Optional `mode` metadata to record with each run (passed through to orchestrator.sweep).")
    ap.add_argument("--iterative", action="store_true", help="Experimental: enable sweep --iterative for each competition.")
    ap.add_argument(
        "--iterative-stage1-seconds",
        type=int,
        default=None,
        help="Optional stage-1 timeout for --iterative (passed through to orchestrator.sweep).",
    )
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--resume-any-status", action="store_true")
    ap.add_argument(
        "--write-leaderboards",
        action="store_true",
        help="If set, write leaderboard artifacts (default: off; see `results.md` and `archive/leaderboards/`).",
    )
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

    models_path = Path(args.models_path)
    if args.preflight and not args.dry_run:
        raw, models = _load_model_set(models_path)
        print(f"preflight: enabled (models={len(models)} timeout={int(args.preflight_timeout_seconds)}s)")
        base_dir = repo_root / "tmp" / "preflight" / "suite"
        base_dir.mkdir(parents=True, exist_ok=True)

        ok_models: list[dict] = []
        failures: list[tuple[str, str, str]] = []
        for m in models:
            provider = m["provider"]
            model_id = m["model_id"]
            r = preflight_one(
                provider=provider,
                model_id=model_id,
                base_dir=base_dir,
                timeout_seconds=int(args.preflight_timeout_seconds),
            )
            if r.status == "ok":
                ok_models.append(m)
            else:
                failures.append((provider, model_id, r.status))
                if args.preflight_fail_fast:
                    break

        if failures and args.preflight_fail_fast:
            joined = ", ".join([f"{p}::{mid}({st})" for p, mid, st in failures])
            raise SystemExit(f"preflight failed: {joined}")

        if not ok_models:
            raise SystemExit("preflight: no models passed")

        if failures:
            print(f"preflight: passed={len(ok_models)} failed={len(failures)} (skipping failed models)")
            for p, mid, st in failures:
                print(f"- preflight FAIL: {p} :: {mid} ({st})")

        filtered = repo_root / "tmp" / "preflight" / "suite_models.filtered.json"
        _write_model_set(dst_path=filtered, raw=raw, models=ok_models)
        print(f"preflight: using filtered models file: {filtered}")
        models_path = filtered

    print(f"suite: {suite_name} ({suite_path})")
    print(f"competitions: {len(competition_ids)}")
    print(f"models_path: {models_path}")
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
            str(models_path),
            "--profile",
            str(args.profile),
            "--runs-per-model",
            str(int(args.runs_per_model)),
            "--db-path",
            str(db_path),
        ]
        if args.budget_seconds is not None:
            cmd += ["--budget-seconds", str(int(args.budget_seconds))]
        if args.prompt_profile is not None:
            cmd += ["--prompt-profile", str(args.prompt_profile)]
        if args.prompt_strategy is not None:
            cmd += ["--prompt-strategy", str(args.prompt_strategy)]
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
        if args.mode:
            cmd += ["--mode", str(args.mode)]
        if args.iterative:
            cmd += ["--iterative"]
            if args.iterative_stage1_seconds is not None:
                cmd += ["--iterative-stage1-seconds", str(int(args.iterative_stage1_seconds))]
        if args.dry_run:
            cmd += ["--dry-run"]

        print(f"\n=== [{i}/{len(competition_ids)}] sweep: {cid} ===")
        if args.dry_run:
            print(" ".join(cmd))
            continue

        proc = subprocess.run(cmd, cwd=repo_root)
        if proc.returncode != 0:
            rc_total = proc.returncode if rc_total == 0 else rc_total

    if not args.dry_run and args.write_leaderboards:
        _refresh_root_leaderboard(repo_root=repo_root, db_path=db_path)
        print(f"\nupdated root leaderboard: {repo_root / 'LEADERBOARD.md'}")
        print(f"updated results leaderboard: {repo_root / 'results' / 'leaderboard.json'}")

    return int(rc_total)


if __name__ == "__main__":
    raise SystemExit(main())
