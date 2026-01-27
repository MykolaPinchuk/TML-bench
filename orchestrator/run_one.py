from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

from orchestrator.db import insert_run
from orchestrator.kilo_cli import run_kilo, write_clean_jsonl
from orchestrator.baselines import ensure_competition_baselines
from orchestrator.leaderboard import LeaderboardPaths, build_leaderboard, load_baselines_df, write_root_leaderboard
from orchestrator.prompting import render_prompt
from orchestrator.provenance import kilo_config_hash, kilo_version, public_manifest
from orchestrator.result import ModelConfig, Provenance, make_result, read_result_json, write_result_json
from orchestrator.run_state import init_run_state, read_run_state, set_run_metadata, start_timer, write_run_state
from orchestrator.run_workspace import copy_public_inputs, create_run_dirs, default_run_id
from orchestrator.schemas import load_spec
from orchestrator.score import score_submission
from orchestrator.validate import validate_and_normalize_submission


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _competition_dir(repo_root: Path, competition_id: str) -> Path:
    return repo_root / "competitions" / competition_id


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_iso_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _headless_end_dt_from_kilo_run(*, state_started_at: str | None, kilo_meta: dict | None) -> datetime | None:
    if not state_started_at or not kilo_meta:
        return None
    dur = kilo_meta.get("duration_seconds")
    if not isinstance(dur, (int, float)):
        return None
    started = _parse_iso_datetime(state_started_at)
    if started is None:
        return None
    return started + timedelta(seconds=float(dur))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_from_run_id(run_id: str) -> int:
    raw = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return max(1, int(raw[:8], 16) % (2**31 - 1))


def _load_kilo_run_meta(run_dir: Path) -> dict | None:
    p = run_dir / "artifacts" / "kilo_run.json"
    if not p.exists():
        return None
    try:
        obj = _read_json(p)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _compute_provenance(
    *,
    spec_path: Path,
    public_dir: Path,
    workspace_dir: Path,
    artifacts_dir: Path,
) -> tuple[Provenance, dict]:
    notes: dict = {}

    spec_sha = _sha256_file(spec_path) if spec_path.exists() else None

    prompt_path = workspace_dir / "RUN_INSTRUCTIONS.md"
    prompt_sha = _sha256_file(prompt_path) if prompt_path.exists() else None

    public_manifest_sha = None
    if public_dir.exists():
        man, man_sha = public_manifest(public_dir=public_dir)
        public_manifest_sha = man_sha
        man_path = artifacts_dir / "public_manifest.json"
        _write_json(man_path, man)
        notes["public_manifest_path"] = str(man_path)
        notes["public_files_count"] = len(man.get("files") or [])

    kv = kilo_version()
    cfg = kilo_config_hash()
    if cfg is not None:
        notes["kilo_config_path"] = cfg.config_path

    return (
        Provenance(
            spec_sha256=spec_sha,
            prompt_sha256=prompt_sha,
            public_manifest_sha256=public_manifest_sha,
            kilo_version=kv,
            kilo_config_sha256=cfg.sha256 if cfg is not None else None,
        ),
        notes,
    )


def _write_and_maybe_record(
    *,
    repo_root: Path,
    competition_id: str,
    result_path: Path,
    result,
    db_path: str | None,
    per_competition: bool,
) -> None:
    write_result_json(result, result_path)
    if not db_path:
        return
    dbp = Path(db_path)
    # Ensure absolute normalization baselines are present (constant+hgb) before writing leaderboards.
    try:
        ensure_competition_baselines(
            db_path=dbp,
            competition_id=competition_id,
            competition_dir=repo_root / "competitions" / competition_id,
            baseline_types=["hgb", "constant"],
            repo_root=repo_root,
        )
    except Exception:  # noqa: BLE001
        pass
    insert_run(dbp, result)
    lb_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard.json",
        csv_path=repo_root / "results" / "leaderboard.csv",
        html_path=repo_root / "results" / "leaderboard.html",
    )
    df = build_leaderboard(db_path=dbp, out_paths=lb_paths, competition_id=competition_id if per_competition else None)
    baselines_df = load_baselines_df(db_path=dbp)
    write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)


def cmd_create(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    budget_seconds = int(getattr(args, "budget_seconds", None) or int(spec.budgets.time_seconds))
    if budget_seconds < 1:
        raise ValueError("--budget-seconds must be >= 1")

    run_id = args.run_id or default_run_id(competition_id=args.competition_id)
    runs_root = repo_root / "runs"
    paths = create_run_dirs(runs_root=runs_root, run_id=run_id)

    copy_public_inputs(competition_dir=competition_dir, workspace_dir=paths.workspace_dir)
    state_path = init_run_state(run_dir=paths.run_dir, time_budget_seconds=budget_seconds)
    state = read_run_state(state_path)
    state = set_run_metadata(
        state,
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    write_run_state(state_path, state)

    prompt = render_prompt(
        base_prompt_path=repo_root / "prompts" / "base_prompt.md",
        override_path=repo_root / "prompts" / "competition_overrides" / f"{args.competition_id}.md",
        time_budget_seconds=budget_seconds,
    )
    paths.instructions_path.write_text(prompt, encoding="utf-8")

    print("Run created.")
    print(f"run_id: {paths.run_id}")
    print(f"workspace: {paths.workspace_dir}")
    print(f"time budget: {budget_seconds} seconds (enforced at finalize)")
    print("before you start Kilo, start the timer:")
    print(f"  python -m orchestrator.run_one start --run-id {paths.run_id}")
    print(f"then: create {paths.workspace_dir/'submission.csv'} (via VSCode/Kilo), then run finalize:")
    print(f"  python -m orchestrator.run_one finalize --competition-id {args.competition_id} --run-id {paths.run_id}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = repo_root / "runs" / args.run_id
    state_path = run_dir / "run_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing run_state.json: {state_path}. Create the run first.")
    state = read_run_state(state_path)
    state = start_timer(state)
    write_run_state(state_path, state)
    print(f"timer started: {args.run_id}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    run_id = args.run_id
    seed = _seed_from_run_id(run_id)
    prompt_profile = getattr(args, "prompt_profile", None)
    run_dir = repo_root / "runs" / run_id
    workspace_dir = run_dir / "workspace"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state_path = run_dir / "run_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing run_state.json: {state_path}. Create the run first.")

    state = read_run_state(state_path)
    state = set_run_metadata(
        state,
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    write_run_state(state_path, state)

    budget_seconds = state.time_budget_seconds
    if state.started_at is None:
        raise RuntimeError(f"Timer not started. Run: python -m orchestrator.run_one start --run-id {run_id}")

    kilo_meta = _load_kilo_run_meta(run_dir)
    provenance, provenance_notes = _compute_provenance(
        spec_path=competition_dir / "spec.yaml",
        public_dir=competition_dir / "public",
        workspace_dir=workspace_dir,
        artifacts_dir=artifacts_dir,
    )

    submission_in = workspace_dir / "submission.csv"
    if not submission_in.exists():
        raise FileNotFoundError(f"Missing submission: {submission_in}")

    # Manual runs: end time derived from submission mtime (ignore finalize delay).
    # Headless runs: use Kilo duration to avoid under-counting time if the agent writes submission early.
    end_dt = _headless_end_dt_from_kilo_run(state_started_at=state.started_at, kilo_meta=kilo_meta) or datetime.fromtimestamp(
        submission_in.stat().st_mtime, tz=timezone.utc
    )
    runtime_seconds = state.elapsed_seconds(now=end_dt)

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
    # Headless runs can exceed by a small amount due to process/clock granularity; allow a tiny grace window.
    grace_seconds = 5.0 if kilo_meta is not None else 0.0
    if runtime_seconds is not None and runtime_seconds > (float(budget_seconds) + float(grace_seconds)):
        model = ModelConfig(
            provider=state.provider or "unknown",
            model_id=state.model_id or "unknown",
            mode=state.mode,
            temperature=state.temperature,
            max_tokens=state.max_tokens,
        ) if (state.provider or state.model_id) else None
        result = make_result(
            competition_id=args.competition_id,
            status="timeout",
            metric_name=None,
            score_raw=None,
            score_normalized=None,
            local_validation_metric=None,
            runtime_seconds=runtime_seconds,
            budget_time_seconds=budget_seconds,
            model=model,
            submission_path=submission_art,
            normalized_submission_path=None,
            repo_root=repo_root,
            run_id_prefix=args.competition_id,
            provenance=provenance,
        )
        result = replace(
            result,
            run_id=run_id,
            seed=seed,
            artifacts=replace(
                result.artifacts,
                notes={
                    **provenance_notes,
                    **({"prompt_profile": prompt_profile} if prompt_profile else {}),
                    "seed": seed,
                },
            )
            if result.artifacts is not None
            else None,
        )
        result_path = run_dir / "result.json"
        _write_and_maybe_record(
            repo_root=repo_root,
            competition_id=args.competition_id,
            result_path=result_path,
            result=result,
            db_path=args.db_path,
            per_competition=args.per_competition,
        )
        extra = f" (grace {grace_seconds:.0f}s)" if grace_seconds else ""
        print(
            f"timeout: runtime_seconds={runtime_seconds:.1f} > budget_seconds={budget_seconds}{extra}; wrote: {result_path}"
        )
        return 3

    if not vr.ok:
        model = ModelConfig(
            provider=state.provider or "unknown",
            model_id=state.model_id or "unknown",
            mode=state.mode,
            temperature=state.temperature,
            max_tokens=state.max_tokens,
        ) if (state.provider or state.model_id) else None
        result = make_result(
            competition_id=args.competition_id,
            status="invalid_submission",
            metric_name=None,
            score_raw=None,
            score_normalized=None,
            local_validation_metric=None,
            runtime_seconds=runtime_seconds,
            budget_time_seconds=budget_seconds,
            model=model,
            submission_path=submission_art,
            normalized_submission_path=None,
            repo_root=repo_root,
            run_id_prefix=args.competition_id,
            provenance=provenance,
        )
        result_path = run_dir / "result.json"
        result = replace(
            result,
            run_id=run_id,
            seed=seed,
            artifacts=replace(
                result.artifacts,
                notes={
                    **provenance_notes,
                    **({"prompt_profile": prompt_profile} if prompt_profile else {}),
                    "seed": seed,
                },
            )
            if result.artifacts is not None
            else None,
        )
        _write_and_maybe_record(
            repo_root=repo_root,
            competition_id=args.competition_id,
            result_path=result_path,
            result=result,
            db_path=args.db_path,
            per_competition=args.per_competition,
        )
        print(f"invalid submission; wrote: {result_path}")
        for e in vr.errors:
            print(f"- {e.code}: {e.message}")
        return 2

    sr = score_submission(spec=spec, private_dir=competition_dir / "private", normalized_submission_csv=normalized_art)
    model = ModelConfig(
        provider=state.provider or "unknown",
        model_id=state.model_id or "unknown",
        mode=state.mode,
        temperature=state.temperature,
        max_tokens=state.max_tokens,
    ) if (state.provider or state.model_id) else None

    submission_sha256 = _sha256_file(submission_art)
    normalized_submission_sha256 = _sha256_file(normalized_art)

    result = make_result(
        competition_id=args.competition_id,
        status="success",
        metric_name=sr.metric_name,
        score_raw=sr.score_raw,
        score_normalized=sr.score_normalized,
        local_validation_metric=None,
        runtime_seconds=runtime_seconds,
        budget_time_seconds=budget_seconds,
        model=model,
        submission_path=submission_art,
        normalized_submission_path=normalized_art,
        repo_root=repo_root,
        run_id_prefix=args.competition_id,
        provenance=provenance,
    )

    # Overwrite run_id to match directory name.
    notes: dict = {
        "submission_sha256": submission_sha256,
        "normalized_submission_sha256": normalized_submission_sha256,
    }
    notes.update(provenance_notes)
    if kilo_meta is not None:
        notes["kilo"] = kilo_meta
    if prompt_profile:
        notes["prompt_profile"] = prompt_profile
    notes["seed"] = seed
    if sr.secondary_metrics and "r2" in sr.secondary_metrics:
        notes["secondary_r2"] = float(sr.secondary_metrics["r2"])
    result = replace(
        result,
        run_id=run_id,
        seed=seed,
        artifacts=replace(
            result.artifacts,
            notes=notes if not result.artifacts.notes else {**result.artifacts.notes, **notes},
        )
        if result.artifacts is not None
        else None,
    )

    result_path = run_dir / "result.json"
    _write_and_maybe_record(
        repo_root=repo_root,
        competition_id=args.competition_id,
        result_path=result_path,
        result=result,
        db_path=args.db_path,
        per_competition=args.per_competition,
    )
    print(f"wrote: {result_path}")
    print(f"private_holdout_{sr.metric_name}: {sr.score_raw}")
    if sr.secondary_metrics and "r2" in sr.secondary_metrics:
        print(f"private_holdout_r2: {sr.secondary_metrics['r2']}")
    print(f"submission_sha256: {submission_sha256[:16]}…")
    if runtime_seconds is not None:
        print(f"runtime_seconds: {runtime_seconds:.1f} (budget {budget_seconds}s)")
    if args.db_path:
        print(f"updated leaderboard under: {(repo_root / 'results')}")
        print(f"updated root leaderboard: {repo_root/'LEADERBOARD.md'}")

    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    spec_budget_seconds = int(spec.budgets.time_seconds)
    budget_seconds = int(getattr(args, "budget_seconds", None) or spec_budget_seconds)
    if budget_seconds < 1:
        raise ValueError("--budget-seconds must be >= 1")

    run_id = args.run_id or default_run_id(competition_id=args.competition_id)
    runs_root = repo_root / "runs"
    paths = create_run_dirs(runs_root=runs_root, run_id=run_id)
    seed = _seed_from_run_id(paths.run_id)

    copy_public_inputs(competition_dir=competition_dir, workspace_dir=paths.workspace_dir)
    state_path = init_run_state(run_dir=paths.run_dir, time_budget_seconds=budget_seconds)
    state = read_run_state(state_path)
    state = set_run_metadata(
        state,
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    state = start_timer(state)
    write_run_state(state_path, state)

    rendered_prompt = render_prompt(
        base_prompt_path=repo_root / "prompts" / "base_prompt.md",
        override_path=repo_root / "prompts" / "competition_overrides" / f"{args.competition_id}.md",
        time_budget_seconds=budget_seconds,
    )
    paths.instructions_path.write_text(rendered_prompt, encoding="utf-8")

    artifacts_dir = paths.artifacts_dir
    kilo_stdout = artifacts_dir / "kilo_stdout.jsonl"
    kilo_stderr = artifacts_dir / "kilo_stderr.log"
    kilo_clean = artifacts_dir / "kilo_stdout.clean.jsonl"

    prompt_profile = getattr(args, "prompt_profile", None) or (
        "sota-xgb" if budget_seconds >= 1200 else ("good-baseline" if budget_seconds >= 600 else "simple-baseline")
    )

    seed_instructions = (
        f"Run metadata:\n- RUN_ID: {paths.run_id}\n- SEED: {seed}\n- PROMPT_PROFILE: {prompt_profile}\n\n"
        f"Use SEED={seed} consistently for any randomness (e.g., `train_test_split(random_state=SEED)`, model `random_state=SEED`, `numpy.random.seed(SEED)`).\n"
    )

    if prompt_profile == "sota-xgb":
        harness_instructions = (
            "Create a single script `train_model.py` that trains on `public/train_public.csv` and writes `submission.csv` matching `public/sample_submission.csv`. "
            "Run `python train_model.py` early to validate the full pipeline end-to-end. "
            "XGBoost is available and allowed for this run. Prefer a strong, reliable baseline first (e.g., `XGBRegressor`/`XGBClassifier`), then iterate (encoding, depth/eta, subsampling, regularization). "
            "Use SEED for all randomness. Always leave a valid `submission.csv` behind. "
            "Do not install packages."
        )
    elif prompt_profile == "good-baseline":
        harness_instructions = (
            "Create a single script `train_model.py` that trains on `public/train_public.csv` and writes `submission.csv` matching `public/sample_submission.csv`. "
            "Run `python train_model.py` early to validate the full pipeline end-to-end. "
            "Then spend most of the remaining time improving performance: do 2–4 quick iterations (encoding/model choice/hyperparameters), and consider light feature engineering. "
            "Prefer scikit-learn options that work well on mixed numeric/categorical data under a time budget (e.g., `HistGradientBoostingRegressor` + `OrdinalEncoder`, or a strong linear baseline like `Ridge`). "
            "Avoid extremely slow approaches unless you keep them small and reliable. Always leave a valid `submission.csv` behind. "
            "Do not install packages."
        )
    else:
        harness_instructions = (
            "Create a single script `train_model.py` that trains on `public/train_public.csv` and writes `submission.csv` matching `public/sample_submission.csv`. "
            "Run `python train_model.py` early to validate the full pipeline end-to-end. "
            "Start with a fast baseline that reliably finishes. Then do a minimal diversity pass: implement exactly TWO candidate models/pipelines and pick the best by local validation using SEED. "
            "Suggested choices: if this looks like regression, try `Ridge` vs `HistGradientBoostingRegressor`; if classification, try `LogisticRegression` vs `HistGradientBoostingClassifier`. "
            "Keep preprocessing simple and fast (numeric: `SimpleImputer`; categorical: `OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)` + `SimpleImputer`). "
            "If validation scores are extremely close, break ties deterministically using SEED (e.g., SEED parity) so different runs don't always choose the same pipeline. "
            "Avoid very slow choices (full `OneHotEncoder` on high-cardinality categoricals, large `RandomForest*`/`ExtraTrees*`, etc.). "
            "If your training run exceeds ~60s, simplify so you always leave a valid `submission.csv` behind. "
            "Do not install packages."
        )

    kilo_prompt = (
        f"Read {paths.instructions_path.name} and follow it exactly.\n"
        "You are running inside a restricted workspace:\n"
        "- Do NOT read or write outside the workspace.\n"
        "- Do NOT use paths with `..` and do NOT run commands like `find ..`.\n"
        "- All required inputs are under `public/` in this workspace.\n\n"
        f"{seed_instructions}\n"
        f"{harness_instructions}\n"
    )
    kilo_timeout = int(args.kilo_timeout_seconds or budget_seconds)

    kr = run_kilo(
        workspace_dir=paths.workspace_dir,
        prompt=kilo_prompt,
        provider_id=args.provider,
        model_id=args.model_id,
        timeout_seconds=kilo_timeout,
        stdout_path=kilo_stdout,
        stderr_path=kilo_stderr,
        stop_when_submission_path=(paths.workspace_dir / "submission.csv") if getattr(args, "stop_when_submission", False) else None,
    )
    _write_json(
        artifacts_dir / "kilo_run.json",
        {
            "argv": kr.argv,
            "returncode": kr.returncode,
            "duration_seconds": kr.duration_seconds,
            "provider_id": args.provider,
            "model_id": args.model_id,
            "timeout_seconds": kilo_timeout,
        },
    )
    try:
        cleaned_events = write_clean_jsonl(src_jsonl=kilo_stdout, dst_jsonl=kilo_clean)
    except Exception:  # noqa: BLE001
        cleaned_events = 0

    submission_in = paths.workspace_dir / "submission.csv"
    if submission_in.exists():
        args2 = argparse.Namespace(
            competition_id=args.competition_id,
            run_id=paths.run_id,
            db_path=args.db_path,
            per_competition=args.per_competition,
            provider=args.provider,
            model_id=args.model_id,
            mode=args.mode,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            prompt_profile=prompt_profile,
        )
        return cmd_finalize(args2)

    runtime_seconds = state.elapsed_seconds(now=_now_utc()) if state.started_at is not None else None
    status = "timeout" if kr.returncode == 124 else "runtime_error"
    model = ModelConfig(
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    provenance, provenance_notes = _compute_provenance(
        spec_path=competition_dir / "spec.yaml",
        public_dir=competition_dir / "public",
        workspace_dir=paths.workspace_dir,
        artifacts_dir=artifacts_dir,
    )
    result = make_result(
        competition_id=args.competition_id,
        status=status,
        metric_name=None,
        score_raw=None,
        score_normalized=None,
        local_validation_metric=None,
        runtime_seconds=runtime_seconds,
        budget_time_seconds=budget_seconds,
        model=model,
        submission_path=None,
        normalized_submission_path=None,
        repo_root=repo_root,
        run_id_prefix=args.competition_id,
        provenance=provenance,
    )
    result = replace(
        result,
        run_id=paths.run_id,
        seed=seed,
        artifacts=replace(
            result.artifacts,
            notes={
                **provenance_notes,
                "prompt_profile": prompt_profile,
                "seed": seed,
                "kilo": {
                    "returncode": kr.returncode,
                    "timeout_seconds": kilo_timeout,
                    "duration_seconds": kr.duration_seconds,
                    "stdout_path": str(kilo_stdout),
                    "stderr_path": str(kilo_stderr),
                    "clean_jsonl_events": cleaned_events,
                    "argv": kr.argv,
                }
            },
        )
        if result.artifacts is not None
        else None,
    )
    result_path = paths.run_dir / "result.json"
    _write_and_maybe_record(
        repo_root=repo_root,
        competition_id=args.competition_id,
        result_path=result_path,
        result=result,
        db_path=args.db_path,
        per_competition=args.per_competition,
    )
    print(f"{status}: no submission.csv produced; wrote: {result_path}")
    return 4 if status == "runtime_error" else 3


def cmd_annotate(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_id = args.run_id
    run_dir = repo_root / "runs" / run_id
    state_path = run_dir / "run_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing run_state.json: {state_path}")

    state = read_run_state(state_path)
    state = set_run_metadata(
        state,
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    write_run_state(state_path, state)
    print(f"updated: {state_path}")

    result_path = run_dir / "result.json"
    if not result_path.exists():
        print(f"note: no result.json found at {result_path}; nothing to update in DB/leaderboard")
        return 0

    result = read_result_json(result_path)
    model = None
    if state.provider and state.model_id:
        model = ModelConfig(
            provider=state.provider,
            model_id=state.model_id,
            mode=state.mode,
            temperature=state.temperature,
            max_tokens=state.max_tokens,
        )
    result = replace(result, model=model)
    write_result_json(result, result_path)
    print(f"updated: {result_path}")

    if args.db_path:
        _write_and_maybe_record(
            repo_root=repo_root,
            competition_id=result.competition_id,
            result_path=result_path,
            result=result,
            db_path=args.db_path,
            per_competition=args.per_competition,
        )
        print(f"updated leaderboard under: {(repo_root / 'results')}")
        print(f"updated root leaderboard: {repo_root/'LEADERBOARD.md'}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a run workspace for a manual VSCode/Kilo agent run.")
    p_create.add_argument("--competition-id", required=True)
    p_create.add_argument("--run-id", default=None)
    p_create.add_argument(
        "--budget-seconds",
        type=int,
        default=None,
        help="Optional override for the run time budget (defaults to spec.yaml budgets.time_seconds).",
    )
    p_create.add_argument("--provider", default=None)
    p_create.add_argument("--model-id", default=None)
    p_create.add_argument("--mode", default=None)
    p_create.add_argument("--temperature", type=float, default=None)
    p_create.add_argument("--max-tokens", type=int, default=None)
    p_create.set_defaults(func=cmd_create)

    p_start = sub.add_parser("start", help="Start the run timer (call immediately before launching Kilo).")
    p_start.add_argument("--run-id", required=True)
    p_start.set_defaults(func=cmd_start)

    p_fin = sub.add_parser("finalize", help="Validate + score a run after submission.csv is produced.")
    p_fin.add_argument("--competition-id", required=True)
    p_fin.add_argument("--run-id", required=True)
    p_fin.add_argument("--db-path", default="results/results.sqlite")
    p_fin.add_argument("--per-competition", action="store_true", help="If set, leaderboard is filtered to this competition only.")
    p_fin.add_argument("--provider", default=None)
    p_fin.add_argument("--model-id", default=None)
    p_fin.add_argument("--mode", default=None)
    p_fin.add_argument("--temperature", type=float, default=None)
    p_fin.add_argument("--max-tokens", type=int, default=None)
    p_fin.set_defaults(func=cmd_finalize)

    p_auto = sub.add_parser("auto", help="Headless run: create → start → run Kilo CLI → finalize.")
    p_auto.add_argument("--competition-id", required=True)
    p_auto.add_argument("--run-id", default=None)
    p_auto.add_argument("--db-path", default="results/results.sqlite")
    p_auto.add_argument("--per-competition", action="store_true", help="If set, leaderboard is filtered to this competition only.")
    p_auto.add_argument("--provider", required=True, help="Kilo provider id (e.g. chutes, nanogpt).")
    p_auto.add_argument("--model-id", required=True, help="Model id to pass to Kilo (provider-specific).")
    p_auto.add_argument("--mode", default=None)
    p_auto.add_argument("--temperature", type=float, default=None)
    p_auto.add_argument("--max-tokens", type=int, default=None)
    p_auto.add_argument(
        "--budget-seconds",
        type=int,
        default=None,
        help="Optional override for the run time budget (defaults to spec.yaml budgets.time_seconds).",
    )
    p_auto.add_argument("--kilo-timeout-seconds", type=int, default=None, help="Optional override for Kilo CLI timeout.")
    p_auto.add_argument(
        "--prompt-profile",
        default=None,
        choices=["simple-baseline", "good-baseline", "sota-xgb"],
        help="Prompt profile for headless runs. If not set, derives from the time budget (>=1200s -> sota-xgb; >=600s -> good-baseline).",
    )
    p_auto.add_argument(
        "--stop-when-submission",
        action="store_true",
        help="If set, terminate the Kilo process shortly after `submission.csv` first appears. Useful for quick smoke runs; disabled by default for sweeps.",
    )
    p_auto.set_defaults(func=cmd_auto)

    p_ann = sub.add_parser("annotate", help="Update a run's model metadata and refresh the leaderboard.")
    p_ann.add_argument("--run-id", required=True)
    p_ann.add_argument("--db-path", default="results/results.sqlite")
    p_ann.add_argument("--per-competition", action="store_true", help="If set, leaderboard is filtered to this run's competition only.")
    p_ann.add_argument("--provider", default=None)
    p_ann.add_argument("--model-id", default=None)
    p_ann.add_argument("--mode", default=None)
    p_ann.add_argument("--temperature", type=float, default=None)
    p_ann.add_argument("--max-tokens", type=int, default=None)
    p_ann.set_defaults(func=cmd_annotate)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
