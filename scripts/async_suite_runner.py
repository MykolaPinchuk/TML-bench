#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_BUDGET_SECONDS = {
    "simple-baseline": 240,
    "good-baseline": 600,
    "sota-xgb": 1200,
}
DEFAULT_PROFILES = ["simple-baseline", "good-baseline", "sota-xgb"]
SYSTEMD_FIELDS = [
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "MainPID",
    "OOMPolicy",
    "MemoryCurrent",
    "MemoryPeak",
    "MemorySwapCurrent",
    "MemoryAvailable",
    "TasksCurrent",
    "CPUUsageNSec",
]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runs_root(repo_root: Path) -> Path:
    return repo_root / "tmp" / "async_runs"


def _run_log_path(run_dir: Path) -> Path:
    return run_dir / "run.log"


def _events_path(run_dir: Path) -> Path:
    return run_dir / "events.jsonl"


def _postmortem_path(run_dir: Path) -> Path:
    return run_dir / "postmortem.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_event(run_dir: Path, event: str, **payload: Any) -> None:
    rec = {"ts": _now_iso(), "event": event}
    rec.update(payload)
    p = _events_path(run_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def _tail(path: Path, n: int = 120) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _systemd_available() -> bool:
    if shutil_which("systemd-run") is None or shutil_which("systemctl") is None:
        return False
    rc = subprocess.run(["systemd-run", "--user", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    return rc == 0


def shutil_which(cmd: str) -> str | None:
    return subprocess.run(["bash", "-lc", f"command -v {shlex.quote(cmd)}"], capture_output=True, text=True).stdout.strip() or None


def _systemd_show(unit: str) -> dict[str, str]:
    cmd = ["systemctl", "--user", "show", unit]
    for f in SYSTEMD_FIELDS:
        cmd.extend(["-p", f])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {}
    out: dict[str, str] = {}
    for ln in proc.stdout.splitlines():
        if "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _systemd_journal_tail(unit: str, *, lines: int = 120) -> list[str]:
    cmd = ["journalctl", "--user", "-u", unit, "--no-pager", "-n", str(int(lines))]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return [ln.rstrip("\n") for ln in proc.stdout.splitlines() if ln.strip()]


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


def _heartbeat_thread(run_dir: Path, stop_event: threading.Event, interval_seconds: int = 20) -> threading.Thread:
    def _loop() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                _update_status(run_dir, heartbeat_at=_now_iso(), heartbeat_pid=os.getpid())
                _append_event(run_dir, "heartbeat", pid=os.getpid())
            except Exception:  # noqa: BLE001
                pass

    t = threading.Thread(target=_loop, name="async-run-heartbeat", daemon=True)
    t.start()
    return t


def _write_postmortem(run_dir: Path, *, extra_notes: list[str] | None = None) -> None:
    status = _load_json(run_dir / "status.json") if (run_dir / "status.json").exists() else {}
    cfg = _load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
    lines: list[str] = []
    lines.append("# Run Postmortem")
    lines.append("")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append(f"- run_name: `{cfg.get('run_name', run_dir.name)}`")
    lines.append(f"- state: `{status.get('state')}`")
    lines.append(f"- pid: `{status.get('pid')}`")
    lines.append(f"- updated_at: `{status.get('updated_at')}`")
    lines.append(f"- started_at: `{status.get('started_at')}`")
    lines.append(f"- finished_at: `{status.get('finished_at')}`")
    lines.append(f"- current_profile: `{status.get('current_profile')}`")
    lines.append(f"- current_attempt: `{status.get('current_attempt')}`")
    lines.append(f"- exit_code: `{status.get('exit_code')}`")
    lines.append("")

    launcher = cfg.get("launcher", {}) if isinstance(cfg.get("launcher"), dict) else {}
    if launcher:
        lines.append("## Launcher")
        for k in sorted(launcher):
            lines.append(f"- {k}: `{launcher.get(k)}`")
        lines.append("")
        if str(launcher.get("method")) == "systemd" and launcher.get("unit"):
            sd = _systemd_show(str(launcher["unit"]))
            if sd:
                lines.append("## systemd status")
                for k in SYSTEMD_FIELDS:
                    lines.append(f"- {k}: `{sd.get(k, '')}`")
                lines.append("")
            jtail = _systemd_journal_tail(str(launcher["unit"]), lines=120)
            if jtail:
                lines.append("## systemd journal tail")
                lines.append("```text")
                lines.extend(jtail[-120:])
                lines.append("```")
                lines.append("")

    if "final_missing" in status:
        lines.append("## final_missing")
        lines.append("```json")
        lines.append(json.dumps(status["final_missing"], indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    attempts = status.get("attempts")
    if isinstance(attempts, dict):
        lines.append("## attempts")
        lines.append("```json")
        lines.append(json.dumps(attempts, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    if extra_notes:
        lines.append("## notes")
        for n in extra_notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## log_tail")
    lines.append("```text")
    lines.extend(_tail(_run_log_path(run_dir), n=120))
    lines.append("```")
    lines.append("")
    _postmortem_path(run_dir).write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        worker_meta={
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "pid": os.getpid(),
            "ppid": os.getppid(),
        },
    )
    _append_event(
        run_dir,
        "worker_start",
        pid=os.getpid(),
        ppid=os.getppid(),
        host=socket.gethostname(),
        platform=platform.platform(),
        python=sys.version.split()[0],
        profiles=profiles,
        mode=mode,
        db_path=str(db_path),
    )

    stop_event = threading.Event()
    hb = _heartbeat_thread(run_dir, stop_event, interval_seconds=20)

    prev_handlers: dict[int, Any] = {}

    def _signal_handler(signum: int, _frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        _append_event(run_dir, "worker_signal", signal=sig_name, signum=signum)
        _update_status(
            run_dir,
            state="aborted",
            abort_signal=sig_name,
            finished_at=_now_iso(),
            failed_reason=f"signal:{sig_name}",
            exit_code=128 + int(signum),
        )
        _write_postmortem(run_dir, extra_notes=[f"Received signal {sig_name}."])
        raise SystemExit(128 + int(signum))

    for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        prev_handlers[s] = signal.getsignal(s)
        signal.signal(s, _signal_handler)

    final_exit = 0
    try:
        for profile in profiles:
            if profile not in PROFILE_BUDGET_SECONDS:
                raise ValueError(f"Unsupported profile: {profile}")
            budget_seconds = int(PROFILE_BUDGET_SECONDS[profile])
            profile_done = False
            _append_event(run_dir, "profile_start", profile=profile, budget_seconds=budget_seconds)

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

                _append_event(
                    run_dir,
                    "profile_attempt_start",
                    profile=profile,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    cmd=cmd,
                )
                print(
                    f"[{_now_iso()}] run profile={profile} attempt={attempt}/{max_attempts} "
                    f"mode={mode} db={db_path}"
                )
                sys.stdout.flush()

                proc = subprocess.run(cmd, cwd=repo_root)
                rc = int(proc.returncode)
                rc_kind = "exit_code" if rc >= 0 else "signal"
                rc_value = rc if rc >= 0 else (-rc)

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
                    "return_kind": rc_kind,
                    "return_value": rc_value,
                    "missing_cells": len(missing),
                    "missing_runs": missing_runs,
                }
                attempts_log[profile].append(summary)
                _update_status(run_dir, attempts=attempts_log, latest_attempt=summary)
                _append_event(run_dir, "profile_attempt_end", profile=profile, **summary)
                print(
                    f"[{summary['finished_at']}] profile={profile} attempt={attempt} rc={rc} "
                    f"missing_cells={summary['missing_cells']} missing_runs={summary['missing_runs']}"
                )
                sys.stdout.flush()

                if summary["missing_cells"] == 0:
                    profile_done = True
                    _append_event(run_dir, "profile_complete", profile=profile, attempt=attempt)
                    break
                if attempt < max_attempts and retry_sleep_seconds > 0:
                    _append_event(
                        run_dir,
                        "profile_retry_sleep",
                        profile=profile,
                        next_attempt=attempt + 1,
                        seconds=retry_sleep_seconds,
                    )
                    time.sleep(retry_sleep_seconds)

            if not profile_done:
                final_exit = 2
                _append_event(run_dir, "profile_incomplete", profile=profile)

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
        _append_event(run_dir, "worker_complete", exit_code=final_exit, final_missing=final_missing)
        _write_postmortem(run_dir)
        return final_exit
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        exc_path = run_dir / "last_exception.txt"
        exc_text = traceback.format_exc()
        exc_path.write_text(exc_text, encoding="utf-8")
        _append_event(run_dir, "worker_exception", error_type=type(e).__name__, error=str(e), exception_file=str(exc_path))
        _update_status(
            run_dir,
            state="failed",
            finished_at=_now_iso(),
            failed_reason=f"exception:{type(e).__name__}",
            exception_file=str(exc_path),
            exit_code=1,
        )
        _write_postmortem(run_dir, extra_notes=[f"Unhandled exception: {type(e).__name__}: {e}"])
        return 1
    finally:
        stop_event.set()
        hb.join(timeout=1.0)
        for s, h in prev_handlers.items():
            signal.signal(s, h)


def _resolve_run_dir(*, repo_root: Path, run_name: str | None, run_dir: str | None) -> Path:
    if run_dir is not None:
        return Path(run_dir).resolve()
    if run_name is None:
        raise ValueError("Provide either --run-name or --run-dir")
    return (_runs_root(repo_root) / run_name).resolve()


def _launch_with_systemd(*, repo_root: Path, run_dir: Path, run_name: str, log_path: Path) -> dict[str, Any]:
    unit = f"tmlbench_async_{run_name.replace('-', '_').replace('.', '_')}"
    env_overrides: dict[str, str] = {}
    for key in ("PATH", "HOME", "PYENV_ROOT", "NVM_DIR", "NVM_BIN", "XDG_RUNTIME_DIR", "PYTHONUNBUFFERED"):
        val = os.environ.get(key)
        if val:
            env_overrides[key] = val
    if "PYTHONUNBUFFERED" not in env_overrides:
        env_overrides["PYTHONUNBUFFERED"] = "1"
    runner_cmd = (
        f"cd {shlex.quote(str(repo_root))} && "
        f"exec {shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} run "
        f"--run-dir {shlex.quote(str(run_dir))} >> {shlex.quote(str(log_path))} 2>&1"
    )
    cmd = [
        "systemd-run",
        "--user",
        "--unit",
        unit,
        "--property",
        "OOMPolicy=continue",
    ]
    for key, value in env_overrides.items():
        cmd.extend(["--setenv", f"{key}={value}"])
    cmd.extend(
        [
            "/bin/bash",
            "-lc",
            runner_cmd,
        ]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
    if proc.returncode != 0:
        raise RuntimeError(f"systemd-run failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
    _append_event(
        run_dir,
        "launcher_start",
        method="systemd",
        unit=unit,
        cmd=cmd,
        env_keys=sorted(env_overrides.keys()),
        stdout=proc.stdout.strip(),
    )
    return {
        "method": "systemd",
        "unit": unit,
        "env_keys": sorted(env_overrides.keys()),
        "launch_stdout": proc.stdout.strip(),
        "launch_stderr": proc.stderr.strip(),
    }


def _launch_with_popen(*, repo_root: Path, run_dir: Path, log_path: Path) -> dict[str, Any]:
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
    _append_event(run_dir, "launcher_start", method="popen", pid=proc.pid, cmd=cmd)
    return {"method": "popen", "pid": int(proc.pid)}


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
    launch_method = str(args.launch_method).strip().lower()
    if launch_method not in {"auto", "systemd", "popen"}:
        raise SystemExit("--launch-method must be one of: auto, systemd, popen")
    if launch_method == "auto":
        launch_method = "systemd" if _systemd_available() else "popen"
    if launch_method == "systemd" and not _systemd_available():
        raise SystemExit("systemd --user is not available; use --launch-method popen")

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
        "launcher": {"method": launch_method},
    }
    _atomic_write_json(run_dir / "config.json", cfg)
    _atomic_write_json(
        run_dir / "status.json",
        {
            "state": "starting",
            "run_name": run_name,
            "created_at": _now_iso(),
            "log_path": str(_run_log_path(run_dir)),
        },
    )
    _append_event(run_dir, "run_created", run_name=run_name, cfg=cfg)

    log_path = _run_log_path(run_dir)
    launch_meta: dict[str, Any]
    if launch_method == "systemd":
        launch_meta = _launch_with_systemd(repo_root=repo_root, run_dir=run_dir, run_name=run_name, log_path=log_path)
    else:
        launch_meta = _launch_with_popen(repo_root=repo_root, run_dir=run_dir, log_path=log_path)

    cfg["launcher"] = launch_meta
    _atomic_write_json(run_dir / "config.json", cfg)

    status_patch = {"state": "running"}
    if "pid" in launch_meta:
        status_patch["pid"] = int(launch_meta["pid"])
    _update_status(run_dir, **status_patch)

    print(f"run_name={run_name}")
    print(f"run_dir={run_dir}")
    print(f"log={log_path}")
    print(f"status={run_dir / 'status.json'}")
    print(f"events={_events_path(run_dir)}")
    print(f"launcher={launch_meta.get('method')}")
    if launch_meta.get("method") == "systemd":
        print(f"systemd_unit={launch_meta.get('unit')}")
    if launch_meta.get("pid"):
        print(f"pid={launch_meta.get('pid')}")
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


def _probe_liveness(run_dir: Path, status: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, dict[str, str], int]:
    launcher = cfg.get("launcher", {}) if isinstance(cfg.get("launcher"), dict) else {}
    method = str(launcher.get("method") or "popen")
    if method == "systemd":
        unit = str(launcher.get("unit") or "")
        sd = _systemd_show(unit) if unit else {}
        main_pid = int(sd.get("MainPID", "0") or "0")
        active_state = sd.get("ActiveState", "")
        alive = active_state in {"active", "activating", "reloading"} or (main_pid > 0 and _is_pid_alive(main_pid))
        return alive, sd, main_pid
    pid = int(status.get("pid") or launcher.get("pid") or 0)
    return _is_pid_alive(pid), {}, pid


def _reconcile_stale_run(run_dir: Path, *, write_postmortem: bool = True) -> dict[str, Any]:
    status_path = run_dir / "status.json"
    cfg_path = run_dir / "config.json"
    if not status_path.exists():
        return {"run_dir": str(run_dir), "changed": False, "reason": "missing_status"}
    status = _load_json(status_path)
    cfg = _load_json(cfg_path) if cfg_path.exists() else {}
    alive, sd, main_pid = _probe_liveness(run_dir, status, cfg)
    changed = False
    if str(status.get("state")) in {"running", "starting"} and not alive:
        reason = "worker_or_launcher_died_without_status_update"
        if sd:
            reason = f"systemd:{sd.get('Result') or 'inactive'}:{sd.get('ExecMainCode','')}:{sd.get('ExecMainStatus','')}"
        _update_status(
            run_dir,
            state="aborted",
            finished_at=_now_iso(),
            failed_reason=reason,
            systemd=sd if sd else None,
            pid=main_pid if main_pid > 0 else status.get("pid"),
        )
        _append_event(run_dir, "reconciled_stale", reason=reason, systemd=sd if sd else None)
        changed = True
        if write_postmortem:
            _write_postmortem(run_dir, extra_notes=[f"Reconciled stale run: {reason}"])
    return {"run_dir": str(run_dir), "changed": changed}


def _cmd_status(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = _resolve_run_dir(repo_root=repo_root, run_name=args.run_name, run_dir=args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")

    _reconcile_stale_run(run_dir, write_postmortem=True)
    status = _load_json(run_dir / "status.json")
    cfg = _load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
    alive, sd, pid = _probe_liveness(run_dir, status, cfg)

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
            f"attempt={la.get('attempt')} rc={la.get('returncode')} "
            f"missing_cells={la.get('missing_cells')} missing_runs={la.get('missing_runs')}"
        )
    if "final_missing" in status:
        print(f"final_missing={json.dumps(status['final_missing'], sort_keys=True)}")
    if sd:
        print(f"systemd_active={sd.get('ActiveState')}")
        print(f"systemd_sub={sd.get('SubState')}")
        print(f"systemd_result={sd.get('Result')}")
        print(f"systemd_exec={sd.get('ExecMainCode')}:{sd.get('ExecMainStatus')}")
    print(f"log={_run_log_path(run_dir)}")
    print(f"events={_events_path(run_dir)}")
    print(f"postmortem={_postmortem_path(run_dir)}")
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
        _reconcile_stale_run(run_dir, write_postmortem=False)
        status = _load_json(status_path)
        cfg = _load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
        alive, _, _ = _probe_liveness(run_dir, status, cfg)
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
    cfg = _load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
    launcher = cfg.get("launcher", {}) if isinstance(cfg.get("launcher"), dict) else {}
    method = str(launcher.get("method") or "popen")

    stopped = False
    if method == "systemd" and launcher.get("unit"):
        unit = str(launcher["unit"])
        rc = subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True, text=True).returncode
        stopped = rc == 0
        _append_event(run_dir, "stop_requested", method="systemd", unit=unit, returncode=rc)
    else:
        pid = int(status.get("pid") or launcher.get("pid") or 0)
        if pid > 0 and _is_pid_alive(pid):
            os.killpg(pid, signal.SIGTERM)
            stopped = True
            _append_event(run_dir, "stop_requested", method="popen", pid=pid)

    if not stopped:
        print("process_not_running")
        _reconcile_stale_run(run_dir, write_postmortem=True)
        return 0
    _update_status(run_dir, state="stopped", finished_at=_now_iso(), stopped_by="operator")
    _write_postmortem(run_dir, extra_notes=["Stopped by operator."])
    print("stopped")
    return 0


def _cmd_diagnose(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_dir = _resolve_run_dir(repo_root=repo_root, run_name=args.run_name, run_dir=args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    _reconcile_stale_run(run_dir, write_postmortem=False)
    _write_postmortem(run_dir)
    print(f"postmortem={_postmortem_path(run_dir)}")
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    rr = _runs_root(repo_root)
    if not rr.exists():
        print("no runs")
        return 0
    changed = 0
    for run_dir in sorted([p for p in rr.iterdir() if p.is_dir()], key=lambda p: p.name):
        res = _reconcile_stale_run(run_dir, write_postmortem=True)
        if res.get("changed"):
            changed += 1
            print(f"reconciled: {run_dir.name}")
    print(f"reconciled_count={changed}")
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
    ap_start.add_argument("--launch-method", default="auto", help="auto|systemd|popen (default: auto)")
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

    ap_stop = sub.add_parser("stop", help="Stop a running async run.")
    ap_stop.add_argument("--run-name", default=None)
    ap_stop.add_argument("--run-dir", default=None)
    ap_stop.set_defaults(fn=_cmd_stop)

    ap_diag = sub.add_parser("diagnose", help="Generate postmortem.md for a run.")
    ap_diag.add_argument("--run-name", default=None)
    ap_diag.add_argument("--run-dir", default=None)
    ap_diag.set_defaults(fn=_cmd_diagnose)

    ap_rec = sub.add_parser("reconcile", help="Mark stale running states as aborted and emit postmortems.")
    ap_rec.set_defaults(fn=_cmd_reconcile)

    return ap


def main() -> int:
    ap = _build_parser()
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
