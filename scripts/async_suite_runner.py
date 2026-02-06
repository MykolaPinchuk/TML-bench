#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_BUDGET_SECONDS = {
    "simple-baseline": 240,
    "good-baseline": 600,
    "sota-xgb": 1200,
}
DEFAULT_PROFILES = ["simple-baseline", "good-baseline", "sota-xgb"]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runs_root(repo_root: Path) -> Path:
    return repo_root / "tmp" / "async_runs"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_suite_competitions(suite_path: Path) -> list[str]:
    raw = _load_json(suite_path)
    competitions = raw.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        raise ValueError(f"Invalid suite file (missing competitions): {suite_path}")
    out: list[str] = []
    for i, comp in enumerate(competitions):
        if not isinstance(comp, str) or not comp.strip():
            raise ValueError(f"Invalid competition at index {i} in {suite_path}")
        out.append(comp.strip())
    return out


def _load_model_keys(models_path: Path) -> list[tuple[str, str]]:
    raw = _load_json(models_path)
    models = raw.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError(f"Invalid models file (missing models): {models_path}")
    out: list[tuple[str, str]] = []
    for i, m in enumerate(models):
        if not isinstance(m, dict):
            raise TypeError(f"Invalid model entry at index {i} in {models_path}")
        provider = str(m.get("provider") or "").strip()
        model_id = str(m.get("model_id") or "").strip()
        if not provider or not model_id:
            raise ValueError(f"Invalid model entry at index {i} in {models_path}")
        out.append((provider, model_id))
    return out


def _missing_cells(
    *,
    db_path: Path,
    competitions: list[str],
    models: list[tuple[str, str]],
    runs_per_model: int,
    prompt_profile: str,
    prompt_strategy: str,
    mode: str,
    budget_seconds: int,
) -> tuple[list[dict[str, Any]], int]:
    expected = [(comp, provider, model_id) for comp in competitions for (provider, model_id) in models]
    if runs_per_model < 1:
        raise ValueError("runs_per_model must be >= 1")
    if not db_path.exists():
        missing = [
            {
                "competition_id": comp,
                "provider": provider,
                "model_id": model_id,
                "have": 0,
                "need": runs_per_model,
            }
            for (comp, provider, model_id) in expected
        ]
        return missing, len(expected) * runs_per_model

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT competition_id, provider, model_id, COUNT(*) AS n
            FROM runs
            WHERE status='success'
              AND prompt_profile=?
              AND prompt_strategy=?
              AND COALESCE(mode, '')=?
              AND budget_time_seconds=?
            GROUP BY competition_id, provider, model_id
            """,
            (prompt_profile, prompt_strategy, mode, int(budget_seconds)),
        )
        counts = {(str(r[0]), str(r[1]), str(r[2])): int(r[3]) for r in cur.fetchall()}
    except sqlite3.OperationalError:
        counts = {}
    finally:
        con.close()

    missing: list[dict[str, Any]] = []
    missing_runs = 0
    for (comp, provider, model_id) in expected:
        have = int(counts.get((comp, provider, model_id), 0))
        if have < runs_per_model:
            need = int(runs_per_model - have)
            missing_runs += need
            missing.append(
                {
                    "competition_id": comp,
                    "provider": provider,
                    "model_id": model_id,
                    "have": have,
                    "need": need,
                }
            )
    return missing, missing_runs


def _update_status(run_dir: Path, **patch: Any) -> None:
    status_path = run_dir / "status.json"
    status: dict[str, Any] = {}
    if status_path.exists():
        try:
            status = _load_json(status_path)
        except Exception:  # noqa: BLE001
            status = {}
    status.update(patch)
    status["updated_at"] = _now_iso()
    _atomic_write_json(status_path, status)


def _run_worker(run_dir: Path) -> int:
    cfg = _load_json(run_dir / "config.json")
    repo_root = Path(cfg["repo_root"])
    suite_path = Path(cfg["suite_path"])
    models_path = Path(cfg["models_path"])
    db_path = Path(cfg["db_path"])
    mode = str(cfg["mode"])
    prompt_strategy = str(cfg["prompt_strategy"])
    runs_per_model = int(cfg["runs_per_model"])
    concurrency = int(cfg["concurrency"])
    max_attempts = int(cfg["max_attempts"])
    retry_sleep_seconds = int(cfg["retry_sleep_seconds"])
    resume_any_status = bool(cfg.get("resume_any_status", False))
    profiles = [str(x) for x in cfg.get("profiles", DEFAULT_PROFILES)]

    competitions = _load_suite_competitions(suite_path)
    models = _load_model_keys(models_path)

    attempts_log: dict[str, list[dict[str, Any]]] = {p: [] for p in profiles}
    _update_status(
        run_dir,
        state="running",
        pid=os.getpid(),
        started_at=_now_iso(),
        current_profile=None,
        current_attempt=None,
        attempts=attempts_log,
    )

    final_exit = 0
    for profile in profiles:
        if profile not in PROFILE_BUDGET_SECONDS:
            raise ValueError(f"Unsupported profile: {profile}")
        budget_seconds = int(PROFILE_BUDGET_SECONDS[profile])
        profile_done = False

        for attempt in range(1, max_attempts + 1):
            _update_status(
                run_dir,
                current_profile=profile,
                current_attempt=attempt,
                state="running",
            )
            cmd = [
                sys.executable,
                "-m",
                "orchestrator.suite",
                "--suite-path",
                str(suite_path),
                "--models-path",
                str(models_path),
                "--profile",
                str(profile),
                "--runs-per-model",
                str(runs_per_model),
                "--concurrency",
                str(concurrency),
                "--prompt-strategy",
                str(prompt_strategy),
                "--db-path",
                str(db_path),
                "--mode",
                str(mode),
                "--resume",
            ]
            if resume_any_status:
                cmd.append("--resume-any-status")

            print(
                f"[{_now_iso()}] run profile={profile} attempt={attempt}/{max_attempts} "
                f"mode={mode} db={db_path}"
            )
            sys.stdout.flush()
            proc = subprocess.run(cmd, cwd=repo_root)
            rc = int(proc.returncode)

            missing, missing_runs = _missing_cells(
                db_path=db_path,
                competitions=competitions,
                models=models,
                runs_per_model=runs_per_model,
                prompt_profile=profile,
                prompt_strategy=prompt_strategy,
                mode=mode,
                budget_seconds=budget_seconds,
            )
            summary = {
                "attempt": attempt,
                "finished_at": _now_iso(),
                "returncode": rc,
                "missing_cells": len(missing),
                "missing_runs": missing_runs,
            }
            attempts_log[profile].append(summary)
            _update_status(
                run_dir,
                attempts=attempts_log,
                latest_attempt=summary,
            )
            print(
                f"[{summary['finished_at']}] profile={profile} attempt={attempt} rc={rc} "
                f"missing_cells={summary['missing_cells']} missing_runs={summary['missing_runs']}"
            )
            sys.stdout.flush()

            if summary["missing_cells"] == 0:
                profile_done = True
                break
            if attempt < max_attempts and retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds)

        if not profile_done:
            final_exit = 2

    final_missing: dict[str, dict[str, int]] = {}
    for profile in profiles:
        missing, missing_runs = _missing_cells(
            db_path=db_path,
            competitions=competitions,
            models=models,
            runs_per_model=runs_per_model,
            prompt_profile=profile,
            prompt_strategy=prompt_strategy,
            mode=mode,
            budget_seconds=int(PROFILE_BUDGET_SECONDS[profile]),
        )
        final_missing[profile] = {"missing_cells": len(missing), "missing_runs": int(missing_runs)}

    _update_status(
        run_dir,
        state="completed" if final_exit == 0 else "failed",
        finished_at=_now_iso(),
        current_profile=None,
        current_attempt=None,
        final_missing=final_missing,
        exit_code=final_exit,
    )
    return final_exit


def _resolve_run_dir(*, repo_root: Path, run_name: str | None, run_dir: str | None) -> Path:
    if run_dir is not None:
        return Path(run_dir).resolve()
    if run_name is None:
        raise ValueError("Provide either --run-name or --run-dir")
    return (_runs_root(repo_root) / run_name).resolve()


def _cmd_start(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    runs_root = _runs_root(repo_root)
    runs_root.mkdir(parents=True, exist_ok=True)

    run_name = str(args.run_name or f"suite_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')}")
    run_dir = (runs_root / run_name).resolve()
    if run_dir.exists():
        raise SystemExit(f"Run already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    profiles = [p.strip() for p in str(args.profiles).split(",") if p.strip()]
    for p in profiles:
        if p not in PROFILE_BUDGET_SECONDS:
            raise SystemExit(f"Unsupported profile: {p}")

    mode = str(args.mode or run_name)
    cfg: dict[str, Any] = {
        "repo_root": str(repo_root),
        "run_name": run_name,
        "suite_path": str(Path(args.suite_path).resolve()),
        "models_path": str(Path(args.models_path).resolve()),
        "db_path": str(Path(args.db_path).resolve()),
        "mode": mode,
        "prompt_strategy": str(args.prompt_strategy),
        "profiles": profiles,
        "runs_per_model": int(args.runs_per_model),
        "concurrency": int(args.concurrency),
        "max_attempts": int(args.max_attempts),
        "retry_sleep_seconds": int(args.retry_sleep_seconds),
        "resume_any_status": bool(args.resume_any_status),
        "created_at": _now_iso(),
    }
    _atomic_write_json(run_dir / "config.json", cfg)
    _atomic_write_json(
        run_dir / "status.json",
        {
            "state": "starting",
            "run_name": run_name,
            "created_at": _now_iso(),
            "log_path": str(run_dir / "run.log"),
        },
    )

    log_path = run_dir / "run.log"
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--run-dir",
        str(run_dir),
    ]
    with log_path.open("a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            cmd,
            cwd=repo_root,
            stdout=lf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    (run_dir / "pid.txt").write_text(str(proc.pid) + "\n", encoding="utf-8")
    _update_status(run_dir, state="running", pid=int(proc.pid))

    print(f"run_name={run_name}")
    print(f"pid={proc.pid}")
    print(f"run_dir={run_dir}")
    print(f"log={log_path}")
    print(f"status={run_dir / 'status.json'}")
    print("")
    print("monitor:")
    print(f"  python scripts/async_suite_runner.py status --run-name {run_name}")
    print(f"  tail -f {log_path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = _resolve_run_dir(repo_root=repo_root, run_name=args.run_name, run_dir=args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    return _run_worker(run_dir)


def _cmd_status(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = _resolve_run_dir(repo_root=repo_root, run_name=args.run_name, run_dir=args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    status = _load_json(run_dir / "status.json")
    cfg = _load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
    pid = int(status.get("pid") or 0)
    alive = _is_pid_alive(pid)

    print(f"run_name={cfg.get('run_name', run_dir.name)}")
    print(f"state={status.get('state')}")
    print(f"pid={pid if pid else 'n/a'}")
    print(f"alive={alive}")
    print(f"updated_at={status.get('updated_at')}")
    print(f"current_profile={status.get('current_profile')}")
    print(f"current_attempt={status.get('current_attempt')}")
    if "latest_attempt" in status:
        la = status["latest_attempt"]
        print(
            "latest_attempt="
            f"profile={status.get('current_profile') or 'completed'} "
            f"attempt={la.get('attempt')} rc={la.get('returncode')} "
            f"missing_cells={la.get('missing_cells')} missing_runs={la.get('missing_runs')}"
        )
    if "final_missing" in status:
        print(f"final_missing={json.dumps(status['final_missing'], sort_keys=True)}")
    print(f"log={run_dir / 'run.log'}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    rr = _runs_root(repo_root)
    if not rr.exists():
        print("no runs")
        return 0
    run_dirs = sorted([p for p in rr.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not run_dirs:
        print("no runs")
        return 0
    for run_dir in run_dirs:
        status_path = run_dir / "status.json"
        if not status_path.exists():
            print(f"{run_dir.name}\tstate=unknown\talive=False")
            continue
        status = _load_json(status_path)
        pid = int(status.get("pid") or 0)
        alive = _is_pid_alive(pid)
        print(
            f"{run_dir.name}\tstate={status.get('state')}\talive={alive}\t"
            f"updated_at={status.get('updated_at')}"
        )
    return 0


def _cmd_stop(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = _resolve_run_dir(repo_root=repo_root, run_name=args.run_name, run_dir=args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    status = _load_json(run_dir / "status.json")
    pid = int(status.get("pid") or 0)
    if pid <= 0 or not _is_pid_alive(pid):
        print("process_not_running")
        return 0
    os.killpg(pid, signal.SIGTERM)
    _update_status(run_dir, state="stopped", finished_at=_now_iso(), stopped_by="operator")
    print(f"stopped pid={pid}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Reliable async launcher for long suite runs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_start = sub.add_parser("start", help="Start a detached suite run.")
    ap_start.add_argument("--run-name", default=None)
    ap_start.add_argument("--suite-path", default="orchestrator/suites/v5_core.json")
    ap_start.add_argument("--models-path", required=True)
    ap_start.add_argument("--db-path", required=True)
    ap_start.add_argument("--mode", default=None)
    ap_start.add_argument("--prompt-strategy", default="profiled1")
    ap_start.add_argument("--profiles", default="simple-baseline,good-baseline,sota-xgb")
    ap_start.add_argument("--runs-per-model", type=int, default=2)
    ap_start.add_argument("--concurrency", type=int, default=3)
    ap_start.add_argument("--max-attempts", type=int, default=3)
    ap_start.add_argument("--retry-sleep-seconds", type=int, default=20)
    ap_start.add_argument("--resume-any-status", action="store_true")
    ap_start.set_defaults(fn=_cmd_start)

    ap_run = sub.add_parser("run", help="Run worker in foreground (used by start).")
    ap_run.add_argument("--run-name", default=None)
    ap_run.add_argument("--run-dir", default=None)
    ap_run.set_defaults(fn=_cmd_run)

    ap_status = sub.add_parser("status", help="Show current status for a run.")
    ap_status.add_argument("--run-name", default=None)
    ap_status.add_argument("--run-dir", default=None)
    ap_status.set_defaults(fn=_cmd_status)

    ap_list = sub.add_parser("list", help="List known async runs.")
    ap_list.set_defaults(fn=_cmd_list)

    ap_stop = sub.add_parser("stop", help="Stop a running async run by PID group.")
    ap_stop.add_argument("--run-name", default=None)
    ap_stop.add_argument("--run-dir", default=None)
    ap_stop.set_defaults(fn=_cmd_stop)

    return ap


def main() -> int:
    ap = _build_parser()
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
