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
from orchestrator.leaderboard import (
    LeaderboardPaths,
    build_leaderboard,
    load_baselines_df,
    write_root_leaderboard,
    write_root_leaderboard_robust,
)
from orchestrator.prompting import render_prompt
from orchestrator.provenance import kilo_config_hash, kilo_version, public_manifest
from orchestrator.result import ModelConfig, Provenance, make_result, read_result_json, write_result_json
from orchestrator.run_state import init_run_state, read_run_state, set_run_metadata, start_timer, write_run_state
from orchestrator.run_workspace import copy_public_inputs, create_run_dirs, default_run_id
from orchestrator.schemas import load_spec
from orchestrator.score import score_submission
from orchestrator.validate import validate_and_normalize_submission
from orchestrator.submission_guard import SubmissionGuard


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _competition_dir(repo_root: Path, competition_id: str) -> Path:
    return repo_root / "competitions" / competition_id


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _prompt_profile_from_budget(*, budget_seconds: int) -> str:
    if int(budget_seconds) >= 1200:
        return "sota-xgb"
    if int(budget_seconds) >= 600:
        return "good-baseline"
    return "simple-baseline"


def _prompt_root(*, repo_root: Path, prompt_strategy: str | None) -> Path:
    sid = str(prompt_strategy or "active").strip()
    if sid in ("", "active"):
        return repo_root / "prompts"
    root = repo_root / "prompts" / "strategies" / sid
    base = root / "base_prompt.md"
    if not base.exists():
        raise FileNotFoundError(f"Invalid --prompt-strategy {sid!r}: missing {base}")
    return root


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
    write_leaderboards: bool,
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
    if not write_leaderboards:
        return
    lb_paths = LeaderboardPaths(
        json_path=repo_root / "results" / "leaderboard.json",
        csv_path=repo_root / "results" / "leaderboard.csv",
        html_path=repo_root / "results" / "leaderboard.html",
    )
    df = build_leaderboard(db_path=dbp, out_paths=lb_paths, competition_id=competition_id if per_competition else None)
    baselines_df = load_baselines_df(db_path=dbp)
    write_root_leaderboard(df=df, repo_root=repo_root, baselines=baselines_df)
    write_root_leaderboard_robust(df=df, repo_root=repo_root, baselines=baselines_df)


def cmd_create(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    competition_dir = _competition_dir(repo_root, args.competition_id)
    spec = load_spec(competition_dir / "spec.yaml")

    budget_seconds = int(getattr(args, "budget_seconds", None) or int(spec.budgets.time_seconds))
    if budget_seconds < 1:
        raise ValueError("--budget-seconds must be >= 1")

    prompt_profile = getattr(args, "prompt_profile", None) or _prompt_profile_from_budget(budget_seconds=budget_seconds)
    prompt_strategy = str(getattr(args, "prompt_strategy", None) or "active").strip()
    prompt_root = _prompt_root(repo_root=repo_root, prompt_strategy=prompt_strategy)

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
        prompt_profile=prompt_profile,
        prompt_strategy=prompt_strategy,
    )
    write_run_state(state_path, state)

    prompt = render_prompt(
        base_prompt_path=prompt_root / "base_prompt.md",
        override_path=prompt_root / "competition_overrides" / f"{args.competition_id}.md",
        profile_path=prompt_root / "prompt_profiles" / f"{prompt_profile}.md",
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
    run_dir = repo_root / "runs" / run_id
    workspace_dir = run_dir / "workspace"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state_path = run_dir / "run_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing run_state.json: {state_path}. Create the run first.")

    state = read_run_state(state_path)
    prompt_profile = getattr(args, "prompt_profile", None) or state.prompt_profile
    prompt_strategy = getattr(args, "prompt_strategy", None) or state.prompt_strategy
    state = set_run_metadata(
        state,
        provider=args.provider,
        model_id=args.model_id,
        mode=args.mode,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        prompt_profile=prompt_profile,
        prompt_strategy=prompt_strategy,
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
            write_leaderboards=bool(getattr(args, "write_leaderboards", False)),
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
            write_leaderboards=bool(getattr(args, "write_leaderboards", False)),
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
    if prompt_strategy:
        notes["prompt_strategy"] = prompt_strategy
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
        write_leaderboards=bool(getattr(args, "write_leaderboards", False)),
    )
    print(f"wrote: {result_path}")
    print(f"private_holdout_{sr.metric_name}: {sr.score_raw}")
    if sr.secondary_metrics and "r2" in sr.secondary_metrics:
        print(f"private_holdout_r2: {sr.secondary_metrics['r2']}")
    print(f"submission_sha256: {submission_sha256[:16]}…")
    if runtime_seconds is not None:
        print(f"runtime_seconds: {runtime_seconds:.1f} (budget {budget_seconds}s)")
    if args.db_path and bool(getattr(args, "write_leaderboards", False)):
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
        prompt_profile=None,
        prompt_strategy=None,
    )
    state = start_timer(state)
    write_run_state(state_path, state)

    prompt_profile = getattr(args, "prompt_profile", None) or _prompt_profile_from_budget(budget_seconds=budget_seconds)
    prompt_strategy = str(getattr(args, "prompt_strategy", None) or "active").strip()
    prompt_root = _prompt_root(repo_root=repo_root, prompt_strategy=prompt_strategy)
    state = read_run_state(state_path)
    state = set_run_metadata(
        state,
        provider=None,
        model_id=None,
        mode=None,
        temperature=None,
        max_tokens=None,
        prompt_profile=prompt_profile,
        prompt_strategy=prompt_strategy,
    )
    write_run_state(state_path, state)

    rendered_prompt = render_prompt(
        base_prompt_path=prompt_root / "base_prompt.md",
        override_path=prompt_root / "competition_overrides" / f"{args.competition_id}.md",
        profile_path=prompt_root / "prompt_profiles" / f"{prompt_profile}.md",
        time_budget_seconds=budget_seconds,
    )
    paths.instructions_path.write_text(rendered_prompt, encoding="utf-8")

    artifacts_dir = paths.artifacts_dir
    kilo_stdout = artifacts_dir / "kilo_stdout.jsonl"
    kilo_stderr = artifacts_dir / "kilo_stderr.log"
    kilo_clean = artifacts_dir / "kilo_stdout.clean.jsonl"

    seed_instructions = (
        f"Run metadata:\n- RUN_ID: {paths.run_id}\n- SEED: {seed}\n- PROMPT_STRATEGY: {prompt_strategy}\n- PROMPT_PROFILE: {prompt_profile}\n\n"
        f"Use SEED={seed} consistently for any randomness (e.g., `train_test_split(random_state=SEED)`, model `random_state=SEED`, `numpy.random.seed(SEED)`).\n"
    )

    # Pass the full rendered prompt directly to Kilo to avoid runs stalling if a model
    # fails to open/read RUN_INSTRUCTIONS.md reliably.
    kilo_prompt = (
        "You are running inside a restricted workspace:\n"
        "- Do NOT read or write outside the workspace.\n"
        "- Do NOT use paths with `..` and do NOT run commands like `find ..`.\n"
        "- All required inputs are under `public/` in this workspace.\n\n"
        f"{rendered_prompt}\n\n"
        f"{seed_instructions}\n"
    )
    kilo_timeout = int(args.kilo_timeout_seconds or budget_seconds)

    iterative = bool(getattr(args, "iterative", False))

    def _stage_header(label: str, *, stage_seconds: int, total_seconds: int) -> str:
        return (
            f"\n# Harness note: {label}\n\n"
            f"- This is a headless benchmark run with a total time budget of {int(total_seconds)} seconds.\n"
            f"- Current stage budget: {int(stage_seconds)} seconds.\n"
            "- Use shell commands only (no IDE/extension tools).\n"
            "- Keep `submission.csv` valid at all times if possible.\n\n"
        )

    def _render_prompt_for(*, profile: str, time_budget_seconds: int) -> str:
        return render_prompt(
            base_prompt_path=prompt_root / "base_prompt.md",
            override_path=prompt_root / "competition_overrides" / f"{args.competition_id}.md",
            profile_path=prompt_root / "prompt_profiles" / f"{profile}.md",
            time_budget_seconds=int(time_budget_seconds),
        )

    def _kilo_prompt_for(*, profile: str, stage_seconds: int, header: str) -> str:
        rendered = _render_prompt_for(profile=profile, time_budget_seconds=int(stage_seconds))
        return (
            "You are running inside a restricted workspace:\n"
            "- Do NOT read or write outside the workspace.\n"
            "- Do NOT use paths with `..` and do NOT run commands like `find ..`.\n"
            "- All required inputs are under `public/` in this workspace.\n\n"
            f"{header}"
            f"{rendered}\n\n"
            f"{seed_instructions}\n"
        )

    def _run_stage(
        *,
        label: str,
        stage_seconds: int,
        profile: str,
        stop_when_submission: bool,
        stdout_path: Path,
        stderr_path: Path,
        clean_path: Path,
    ):
        header = _stage_header(label, stage_seconds=int(stage_seconds), total_seconds=int(budget_seconds))
        prompt = _kilo_prompt_for(profile=profile, stage_seconds=int(stage_seconds), header=header)
        kr = run_kilo(
            workspace_dir=paths.workspace_dir,
            prompt=prompt,
            provider_id=args.provider,
            model_id=args.model_id,
            timeout_seconds=int(stage_seconds),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            stop_when_submission_path=(paths.workspace_dir / "submission.csv") if stop_when_submission else None,
        )
        try:
            cleaned_events = write_clean_jsonl(src_jsonl=stdout_path, dst_jsonl=clean_path)
        except Exception:  # noqa: BLE001
            cleaned_events = 0
        return kr, cleaned_events

    guard: SubmissionGuard | None = None
    spec = load_spec(competition_dir / "spec.yaml")
    if iterative:
        guard = SubmissionGuard(
            spec=spec,
            public_dir=competition_dir / "public",
            workspace_dir=paths.workspace_dir,
            artifacts_dir=artifacts_dir,
        )
        guard.start()

    stages_meta: list[dict] = []
    total_duration = 0.0
    stop_reason: str | None = None

    if not iterative:
        kr, cleaned_events = _run_stage(
            label="Single-stage run",
            stage_seconds=int(kilo_timeout),
            profile=prompt_profile,
            stop_when_submission=bool(getattr(args, "stop_when_submission", False)),
            stdout_path=kilo_stdout,
            stderr_path=kilo_stderr,
            clean_path=kilo_clean,
        )
        stages_meta.append(
            {
                "label": "single",
                "profile": prompt_profile,
                "timeout_seconds": int(kilo_timeout),
                "returncode": int(kr.returncode),
                "stop_reason": kr.stop_reason,
                "duration_seconds": float(kr.duration_seconds),
                "stdout_path": str(kilo_stdout),
                "stderr_path": str(kilo_stderr),
                "clean_jsonl_events": int(cleaned_events),
                "argv": kr.argv,
            }
        )
        total_duration += float(kr.duration_seconds)
        stop_reason = kr.stop_reason
    else:
        # Stage 1: get a valid submission quickly, then continue for improvement.
        stage1_seconds = getattr(args, "iterative_stage1_seconds", None)
        if stage1_seconds is None:
            stage1_seconds = max(60, int(round(0.2 * float(budget_seconds))))
            stage1_seconds = min(int(stage1_seconds), 240)
        stage1_seconds = int(max(30, min(int(stage1_seconds), int(budget_seconds))))
        # Stage-2 gets the *remaining* time after stage-1 actually finishes.
        # This avoids wasting budget when stage-1 stops early (e.g., once `submission.csv` appears).
        stage2_seconds_planned = int(max(0, int(budget_seconds) - int(stage1_seconds)))

        out1 = artifacts_dir / "kilo_stdout.stage1.jsonl"
        err1 = artifacts_dir / "kilo_stderr.stage1.log"
        clean1 = artifacts_dir / "kilo_stdout.stage1.clean.jsonl"
        kr1, cleaned1 = _run_stage(
            label="Stage 1/2: bootstrap a valid submission quickly",
            stage_seconds=stage1_seconds,
            profile="simple-baseline",
            stop_when_submission=True,
            stdout_path=out1,
            stderr_path=err1,
            clean_path=clean1,
        )
        stages_meta.append(
            {
                "label": "stage1",
                "profile": "simple-baseline",
                "timeout_seconds": int(stage1_seconds),
                "returncode": int(kr1.returncode),
                "stop_reason": kr1.stop_reason,
                "duration_seconds": float(kr1.duration_seconds),
                "stdout_path": str(out1),
                "stderr_path": str(err1),
                "clean_jsonl_events": int(cleaned1),
                "argv": kr1.argv,
            }
        )
        total_duration += float(kr1.duration_seconds)
        if kr1.stop_reason == "api_402":
            stop_reason = "api_402"

        out2 = artifacts_dir / "kilo_stdout.stage2.jsonl"
        err2 = artifacts_dir / "kilo_stderr.stage2.log"
        clean2 = artifacts_dir / "kilo_stdout.stage2.clean.jsonl"
        stage2_seconds = int(max(0, int(budget_seconds) - int(round(total_duration))))
        # Keep the old planned value as a lower bound (for backward-compat thinking),
        # but let stage2 consume extra remaining time if stage1 stopped early.
        stage2_seconds = int(max(int(stage2_seconds), int(stage2_seconds_planned)))
        if stop_reason != "api_402" and stage2_seconds >= 1:
            kr2, cleaned2 = _run_stage(
                label="Stage 2/2: continue improving, but keep submission valid",
                stage_seconds=stage2_seconds,
                profile=prompt_profile,
                stop_when_submission=False,
                stdout_path=out2,
                stderr_path=err2,
                clean_path=clean2,
            )
            stages_meta.append(
                {
                    "label": "stage2",
                    "profile": prompt_profile,
                    "timeout_seconds": int(stage2_seconds),
                    "returncode": int(kr2.returncode),
                    "stop_reason": kr2.stop_reason,
                    "duration_seconds": float(kr2.duration_seconds),
                    "stdout_path": str(out2),
                    "stderr_path": str(err2),
                    "clean_jsonl_events": int(cleaned2),
                    "argv": kr2.argv,
                }
            )
            total_duration += float(kr2.duration_seconds)
            if stop_reason is None:
                stop_reason = kr2.stop_reason

        # Restore the last known valid submission if the final file is missing/invalid.
        if guard is not None:
            guard.ensure_workspace_has_valid_submission()

        # For backward compatibility with code that expects these names.
        # (They may be large; keep them as small summaries for this run.)
        src_out = out2 if out2.exists() else out1
        src_err = err2 if err2.exists() else err1
        if src_out.exists():
            try:
                shutil.copyfile(src_out, kilo_stdout)
            except Exception:
                pass
        if src_err.exists():
            try:
                shutil.copyfile(src_err, kilo_stderr)
            except Exception:
                pass
        try:
            cleaned_events = write_clean_jsonl(src_jsonl=src_out if src_out.exists() else out1, dst_jsonl=kilo_clean)
        except Exception:  # noqa: BLE001
            cleaned_events = 0

    if guard is not None:
        guard.stop()
        guard_stats = guard.stats()
    else:
        guard_stats = None

    # Persist a single summary file used by finalize to derive headless runtime.
    _write_json(
        artifacts_dir / "kilo_run.json",
        {
            "argv": stages_meta[-1]["argv"] if stages_meta else [],
            "returncode": int(stages_meta[-1]["returncode"]) if stages_meta else 0,
            "duration_seconds": float(total_duration),
            "stop_reason": stop_reason,
            "provider_id": args.provider,
            "model_id": args.model_id,
            "timeout_seconds": int(kilo_timeout),
            "stages": stages_meta,
            "submission_guard": {
                "valid_snapshots": guard_stats.valid_snapshots,
                "last_valid_path": guard_stats.last_valid_path,
                "last_valid_normalized_path": guard_stats.last_valid_normalized_path,
            }
            if guard_stats is not None
            else None,
        },
    )

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
            prompt_strategy=prompt_strategy,
        )
        return cmd_finalize(args2)

    runtime_seconds = state.elapsed_seconds(now=_now_utc()) if state.started_at is not None else None
    if stop_reason == "api_402":
        status = "provider_error"
    else:
        # For iterative runs, if any stage hit the Kilo timeout boundary, treat as timeout.
        last_rc = int(stages_meta[-1]["returncode"]) if stages_meta else 0
        status = "timeout" if last_rc == 124 else "runtime_error"
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
                "prompt_strategy": prompt_strategy,
                "seed": seed,
                "kilo": {
                    "returncode": int(stages_meta[-1]["returncode"]) if stages_meta else None,
                    "timeout_seconds": kilo_timeout,
                    "duration_seconds": float(total_duration),
                    "stdout_path": str(kilo_stdout),
                    "stderr_path": str(kilo_stderr),
                    "clean_jsonl_events": cleaned_events,
                    "argv": stages_meta[-1]["argv"] if stages_meta else [],
                    "stages": stages_meta,
                    "submission_guard": {
                        "valid_snapshots": guard_stats.valid_snapshots,
                        "last_valid_path": guard_stats.last_valid_path,
                        "last_valid_normalized_path": guard_stats.last_valid_normalized_path,
                    }
                    if guard_stats is not None
                    else None,
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
        write_leaderboards=bool(getattr(args, "write_leaderboards", False)),
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
        prompt_profile=None,
        prompt_strategy=None,
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
            write_leaderboards=True,
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
    p_create.add_argument(
        "--prompt-profile",
        default=None,
        help=(
            "Prompt profile id (file in `prompts/prompt_profiles/<id>.md`). "
            "If not set, derives from time budget (>=1200s -> sota-xgb; >=600s -> good-baseline; else simple-baseline)."
        ),
    )
    p_create.add_argument(
        "--prompt-strategy",
        default="active",
        help="Prompt strategy id. `active` uses the live `prompts/` folder; otherwise uses `prompts/strategies/<id>/`.",
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
    p_fin.add_argument(
        "--write-leaderboards",
        action="store_true",
        help="If set, write leaderboard artifacts (default: off; see `results.md` and `archive/leaderboards/`).",
    )
    p_fin.add_argument(
        "--prompt-profile",
        default=None,
        help="Optional prompt profile metadata to record with the run (useful for manual runs).",
    )
    p_fin.add_argument(
        "--prompt-strategy",
        default=None,
        help="Optional prompt strategy metadata to record with the run (defaults to the value recorded in run_state.json).",
    )
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
    p_auto.add_argument(
        "--write-leaderboards",
        action="store_true",
        help="If set, write leaderboard artifacts (default: off; see `results.md` and `archive/leaderboards/`).",
    )
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
        help=(
            "Prompt profile id (file in `prompts/prompt_profiles/<id>.md`) for headless runs. "
            "If not set, derives from time budget (>=1200s -> sota-xgb; >=600s -> good-baseline; else simple-baseline)."
        ),
    )
    p_auto.add_argument(
        "--prompt-strategy",
        default="active",
        help="Prompt strategy id. `active` uses the live `prompts/` folder; otherwise uses `prompts/strategies/<id>/`.",
    )
    p_auto.add_argument(
        "--stop-when-submission",
        action="store_true",
        help="If set, terminate the Kilo process shortly after `submission.csv` first appears. Useful for quick smoke runs; disabled by default for sweeps.",
    )
    p_auto.add_argument(
        "--iterative",
        action="store_true",
        help="Experimental: two-stage headless run (bootstrap a valid submission quickly, then continue improving) with a validity guard for `submission.csv`.",
    )
    p_auto.add_argument(
        "--iterative-stage1-seconds",
        type=int,
        default=None,
        help="Optional stage-1 timeout for --iterative. Default: min(240, max(60, 0.2*budget)).",
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
