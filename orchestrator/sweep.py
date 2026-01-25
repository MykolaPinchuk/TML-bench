from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from orchestrator.db import insert_run
from orchestrator.leaderboard import LeaderboardPaths, build_leaderboard, write_root_leaderboard
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 3: batch runs via Kilo CLI (no Docker).")
    ap.add_argument("--competition-id", required=True)
    ap.add_argument(
        "--models-path",
        default=str(_repo_root() / "orchestrator" / "model_sets" / "v3_fast.json"),
        help="JSON file with provider/model_id entries.",
    )
    ap.add_argument("--runs-per-model", type=int, default=1)
    ap.add_argument("--db-path", default="results/results.sqlite")
    ap.add_argument("--per-competition", action="store_true")
    ap.add_argument("--kilo-timeout-seconds", type=int, default=None)
    ap.add_argument("--only-provider", default=None, help="If set, only run models from this provider id.")
    ap.add_argument("--max-models", type=int, default=None, help="If set, limit to the first N models selected.")
    ap.add_argument("--max-runs", type=int, default=None, help="If set, stop after N total runs (across all models).")
    ap.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="If >1, run multiple headless runs in parallel. DB/leaderboard updates are done once at the end.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
    if args.concurrency < 1:
        raise ValueError("--concurrency must be >= 1")

    planned = [(m["provider"], m["model_id"]) for m in models for _ in range(args.runs_per_model)]
    if args.max_runs is not None:
        if args.max_runs < 0:
            raise ValueError("--max-runs must be >= 0")
        planned = planned[: args.max_runs]
    print(f"competition: {args.competition_id}")
    print(f"models: {len(models)} from {model_set_path}")
    print(f"total runs: {len(planned)} (runs_per_model={args.runs_per_model})")

    if args.dry_run:
        for provider, model_id in planned:
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
            kilo_timeout_seconds=args.kilo_timeout_seconds,
        )
        rc = int(cmd_auto(ns))
        return run_id, rc

    failures = 0
    run_ids: list[str] = []

    if args.concurrency <= 1:
        run_n = 0
        for m in models:
            for rep in range(args.runs_per_model):
                if args.max_runs is not None and run_n >= args.max_runs:
                    break
                run_n += 1
                run_id = default_run_id(competition_id=args.competition_id)
                run_ids.append(run_id)
                print(f"\n=== run {run_n}/{len(planned)}: {m['provider']} :: {m['model_id']} (rep {rep+1}) ===")
                try:
                    _, rc = _run_one(provider=m["provider"], model_id=m["model_id"], run_id=run_id)
                except Exception as e:  # noqa: BLE001
                    failures += 1
                    print(f"error: {type(e).__name__}: {e}")
                    continue
                if rc != 0:
                    failures += 1
                    print(f"nonzero exit: {rc}")
            if args.max_runs is not None and run_n >= args.max_runs:
                break
    else:
        tasks: list[tuple[str, str, str]] = []
        run_n = 0
        for m in models:
            for rep in range(args.runs_per_model):
                if args.max_runs is not None and run_n >= args.max_runs:
                    break
                run_n += 1
                run_id = default_run_id(competition_id=args.competition_id)
                tasks.append((m["provider"], m["model_id"], run_id))
            if args.max_runs is not None and run_n >= args.max_runs:
                break

        print(f"concurrency: {args.concurrency} (DB/leaderboard updated after runs complete)")
        for i, (provider, model_id, run_id) in enumerate(tasks, start=1):
            print(f"- scheduled {i}/{len(tasks)}: {provider} :: {model_id} (run_id {run_id})")

        with ThreadPoolExecutor(max_workers=int(args.concurrency)) as ex:
            futs = [ex.submit(_run_one, provider=p, model_id=m, run_id=r) for (p, m, r) in tasks]
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
            write_root_leaderboard(df=df, repo_root=repo_root)
            print(f"updated leaderboard under: {(repo_root / 'results')}")
            print(f"updated root leaderboard: {repo_root/'LEADERBOARD.md'}")

    if failures:
        print(f"\ncompleted with failures={failures}")
        return 2
    print("\ncompleted OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
