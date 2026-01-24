from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestrator.run_one import cmd_auto


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

    failures = 0
    run_n = 0
    for m in models:
        for rep in range(args.runs_per_model):
            if args.max_runs is not None and run_n >= args.max_runs:
                break
            run_n += 1
            print(f"\n=== run {run_n}/{len(planned)}: {m['provider']} :: {m['model_id']} (rep {rep+1}) ===")
            ns = argparse.Namespace(
                competition_id=args.competition_id,
                run_id=None,
                db_path=args.db_path,
                per_competition=args.per_competition,
                provider=m["provider"],
                model_id=m["model_id"],
                mode=None,
                temperature=None,
                max_tokens=None,
                kilo_timeout_seconds=args.kilo_timeout_seconds,
            )
            try:
                rc = int(cmd_auto(ns))
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"error: {type(e).__name__}: {e}")
                continue
            if rc != 0:
                failures += 1
                print(f"nonzero exit: {rc}")
        if args.max_runs is not None and run_n >= args.max_runs:
            break

    if failures:
        print(f"\ncompleted with failures={failures}")
        return 2
    print("\ncompleted OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
