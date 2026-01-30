from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from orchestrator.db import ensure_db, fetch_runs, insert_run
from orchestrator.baselines import ensure_competition_baselines
from orchestrator.leaderboard import (
    LeaderboardPaths,
    build_leaderboard,
    load_baselines_df,
    write_root_leaderboard,
    write_root_leaderboard_robust,
)
from orchestrator.result import read_result_json
from orchestrator.run_one import cmd_auto
from orchestrator.run_workspace import default_run_id


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_model_set(path: Path) -> list[dict]:
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
    return out


def _profile_budget_seconds(profile: str) -> int:
    if profile == "simple-baseline":
        return 240
    if profile == "good-baseline":
        return 600
    if profile == "sota-xgb":
        return 1200
    raise ValueError(f"Unknown profile: {profile}")


def _derive_prompt_profile(*, budget_seconds: int) -> str:
    if int(budget_seconds) >= 1200:
        return "sota-xgb"
    if int(budget_seconds) >= 600:
        return "good-baseline"
    return "simple-baseline"


def _resume_counts_by_model(
    *,
    db_path: str | Path,
    competition_id: str,
    budget_seconds: int,
    prompt_profile: str,
    any_status: bool,
) -> dict[tuple[str, str], int]:
    ensure_db(db_path)
    rows = fetch_runs(db_path, competition_id=competition_id)

    counts: dict[tuple[str, str], int] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        provider = str(r.get("provider") or "").strip()
        model_id = str(r.get("model_id") or "").strip()
        if not provider or not model_id:
            continue

        if str(r.get("prompt_profile") or "").strip() != str(prompt_profile):
            continue

        try:
            b = int(r.get("budget_time_seconds"))
        except Exception:  # noqa: BLE001
            continue
        if b != int(budget_seconds):
            continue

        status = str(r.get("status") or "").strip()
        if not any_status and status != "success":
            continue

        key = (provider, model_id)
        counts[key] = int(counts.get(key, 0) + 1)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 3: batch runs via Kilo CLI (no Docker).")
    ap.add_argument("--competition-id", required=True)
    ap.add_argument(
        "--models-path",
        default=str(_repo_root() / "orchestrator" / "model_sets" / "v3_fast.json"),
        help="JSON file with provider/model_id entries.",
    )
    ap.add_argument(
        "--profile",
        default=None,
        choices=["simple-baseline", "good-baseline", "sota-xgb"],
        help="Optional sweep profile. `simple-baseline` targets 240s. `good-baseline` targets 600s. `sota-xgb` targets 1200s.",
    )
    ap.add_argument("--runs-per-model", type=int, default=1)
    ap.add_argument("--db-path", default="results/results.sqlite")
    ap.add_argument("--per-competition", action="store_true")
    ap.add_argument(
        "--budget-seconds",
        type=int,
        default=None,
        help="Optional override for the run time budget (defaults to competition spec.yaml budgets.time_seconds).",
    )
    ap.add_argument("--kilo-timeout-seconds", type=int, default=None)
    ap.add_argument(
        "--prompt-profile",
        default=None,
        choices=["simple-baseline", "good-baseline", "sota-xgb"],
        help="Prompt profile to pass to `run_one auto`. If not set, derives from `--profile` (if provided).",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="If set, only schedule missing runs by looking at existing runs in --db-path (counts only successes by default).",
    )
    ap.add_argument(
        "--resume-any-status",
        action="store_true",
        help="If set with --resume, count any prior run status (success/timeout/invalid/...) toward --runs-per-model.",
    )
    ap.add_argument("--only-provider", default=None, help="If set, only run models from this provider id.")
    ap.add_argument("--max-models", type=int, default=None, help="If set, limit to the first N models selected.")
    ap.add_argument("--max-runs", type=int, default=None, help="If set, stop after N total runs (across all models).")
    ap.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="If >1, run multiple headless runs in parallel. Default: 5 if >4 models selected, else 4. DB/leaderboard updates are done once at the end.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.profile is not None:
        if args.budget_seconds is None:
            args.budget_seconds = _profile_budget_seconds(args.profile)
        if args.kilo_timeout_seconds is None:
            args.kilo_timeout_seconds = int(args.budget_seconds)
        if args.prompt_profile is None:
            args.prompt_profile = args.profile
    if args.prompt_profile is None and args.budget_seconds is not None:
        args.prompt_profile = _derive_prompt_profile(budget_seconds=int(args.budget_seconds))

    repo_root = _repo_root()
    competition_dir = repo_root / "competitions" / args.competition_id
    public_dir = competition_dir / "public"
    if not public_dir.exists():
        raise FileNotFoundError(
            f"Missing competition public dir: {public_dir}. Run the competition's prepare_competition.py first."
        )

    model_set_path = Path(args.models_path)
    models = _load_model_set(model_set_path)
    if args.only_provider:
        models = [m for m in models if m["provider"] == args.only_provider]
    if args.max_models is not None:
        if args.max_models < 0:
            raise ValueError("--max-models must be >= 0")
        models = models[: args.max_models]
    if not models:
        raise ValueError("No models selected to run.")

    if args.runs_per_model < 1:
        raise ValueError("--runs-per-model must be >= 1")
    if args.concurrency is None:
        args.concurrency = 5 if len(models) > 4 else 4
    if int(args.concurrency) < 1:
        raise ValueError("--concurrency must be >= 1")
    args.concurrency = int(args.concurrency)

    if args.resume and (args.budget_seconds is None or args.prompt_profile is None):
        raise ValueError("--resume requires --budget-seconds (or --profile) so runs can be matched deterministically.")

    resume_counts = (
        _resume_counts_by_model(
            db_path=args.db_path,
            competition_id=args.competition_id,
            budget_seconds=int(args.budget_seconds),
            prompt_profile=str(args.prompt_profile),
            any_status=bool(args.resume_any_status),
        )
        if args.resume and args.db_path
        else {}
    )

    tasks: list[tuple[str, str]] = []
    for m in models:
        key = (m["provider"], m["model_id"])
        have = int(resume_counts.get(key, 0)) if args.resume else 0
        need = max(0, int(args.runs_per_model) - have)
        for _ in range(need):
            tasks.append((m["provider"], m["model_id"]))

    if args.max_runs is not None:
        if args.max_runs < 0:
            raise ValueError("--max-runs must be >= 0")
        tasks = tasks[: args.max_runs]
    print(f"competition: {args.competition_id}")
    print(f"models: {len(models)} from {model_set_path}")
    if args.resume:
        print(f"resume: enabled ({'any status' if args.resume_any_status else 'success only'})")
    if args.budget_seconds is not None:
        print(f"budget_seconds: {int(args.budget_seconds)}")
    if args.prompt_profile is not None:
        print(f"prompt_profile: {args.prompt_profile}")
    print(f"total runs: {len(tasks)} (runs_per_model={args.runs_per_model})")

    if args.dry_run:
        for provider, model_id in tasks:
            print(f"- {provider} :: {model_id}")
        return 0

    def _run_one(*, provider: str, model_id: str, run_id: str) -> tuple[str, int]:
        ns = argparse.Namespace(
            competition_id=args.competition_id,
            run_id=run_id,
            # In parallel mode, avoid sqlite write contention by recording to DB once at the end.
            db_path=args.db_path if args.concurrency <= 1 else None,
            per_competition=args.per_competition,
            provider=provider,
            model_id=model_id,
            mode=None,
            temperature=None,
            max_tokens=None,
            budget_seconds=args.budget_seconds,
            kilo_timeout_seconds=args.kilo_timeout_seconds,
            prompt_profile=args.prompt_profile,
        )
        rc = int(cmd_auto(ns))
        return run_id, rc

    failures = 0
    run_ids: list[str] = []

    if args.concurrency <= 1:
        for run_n, (provider, model_id) in enumerate(tasks, start=1):
            run_id = default_run_id(competition_id=args.competition_id)
            run_ids.append(run_id)
            print(f"\n=== run {run_n}/{len(tasks)}: {provider} :: {model_id} ===")
            try:
                _, rc = _run_one(provider=provider, model_id=model_id, run_id=run_id)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"error: {type(e).__name__}: {e}")
                continue
            if rc != 0:
                failures += 1
                print(f"nonzero exit: {rc}")
    else:
        scheduled: list[tuple[str, str, str]] = []
        for provider, model_id in tasks:
            run_id = default_run_id(competition_id=args.competition_id)
            scheduled.append((provider, model_id, run_id))

        print(f"concurrency: {args.concurrency} (DB/leaderboard updated after runs complete)")
        for i, (provider, model_id, run_id) in enumerate(scheduled, start=1):
            print(f"- scheduled {i}/{len(scheduled)}: {provider} :: {model_id} (run_id {run_id})")

        with ThreadPoolExecutor(max_workers=int(args.concurrency)) as ex:
            futs = [ex.submit(_run_one, provider=p, model_id=m, run_id=r) for (p, m, r) in scheduled]
            for fut in as_completed(futs):
                try:
                    run_id, rc = fut.result()
                except Exception as e:  # noqa: BLE001
                    failures += 1
                    print(f"error: {type(e).__name__}: {e}")
                    continue
                run_ids.append(run_id)
                if rc != 0:
                    failures += 1
                    print(f"nonzero exit: {rc} (run_id {run_id})")

        # Import results into DB/leaderboards once, deterministically.
        if args.db_path:
            dbp = Path(args.db_path)
            try:
                ensure_competition_baselines(
                    db_path=dbp,
                    competition_id=args.competition_id,
                    competition_dir=repo_root / "competitions" / args.competition_id,
                    baseline_types=["hgb", "constant"],
                    repo_root=repo_root,
                )
            except Exception:  # noqa: BLE001
                pass
            for run_id in run_ids:
                result_path = repo_root / "runs" / run_id / "result.json"
                if not result_path.exists():
                    continue
                rr = read_result_json(result_path)
                insert_run(dbp, rr)

            lb_paths = LeaderboardPaths(
                json_path=repo_root / "results" / "leaderboard.json",
                csv_path=repo_root / "results" / "leaderboard.csv",
                html_path=repo_root / "results" / "leaderboard.html",
            )
            df = build_leaderboard(
                db_path=dbp,
                out_paths=lb_paths,
                competition_id=args.competition_id if args.per_competition else None,
            )
            baselines_df = load_baselines_df(db_path=dbp)
            write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)
            write_root_leaderboard_robust(df=df, repo_root=repo_root, baselines=baselines_df)
            print(f"updated leaderboard under: {(repo_root / 'results')}")
            print(f"updated root leaderboard: {repo_root/'LEADERBOARD.md'}")

    if failures:
        print(f"\ncompleted with failures={failures}")
        return 2
    print("\ncompleted OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
