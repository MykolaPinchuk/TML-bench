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
from datetime import datetime, timedelta
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
    "Restart",
    "RestartUSec",
    "NRestarts",
    "MainPID",
    "OOMPolicy",
    "MemoryHigh",
    "MemoryMax",
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


def _which_in_path(cmd: str, path_value: str) -> str | None:
    env = dict(os.environ)
    env["PATH"] = path_value
    proc = subprocess.run(
        ["bash", "-lc", f"command -v {shlex.quote(cmd)}"],
        capture_output=True,
        text=True,
        env=env,
    )
    out = (proc.stdout or "").strip()
    return out or None


def _augment_path_for_kilo(
    *,
    path_value: str,
    home: str | None,
    nvm_dir: str | None,
    nvm_bin: str | None,
) -> tuple[str, list[str], str | None]:
    parts = [p for p in path_value.split(":") if p]
    seen = set(parts)
    added: list[str] = []
    candidates: list[str] = []

    if nvm_bin:
        candidates.append(nvm_bin)
    if nvm_dir:
        base = Path(nvm_dir) / "versions" / "node"
        if base.exists():
            for p in sorted(base.glob("*/bin"), reverse=True):
                candidates.append(str(p))
    if home:
        base = Path(home) / ".nvm" / "versions" / "node"
        if base.exists():
            for p in sorted(base.glob("*/bin"), reverse=True):
                candidates.append(str(p))

    for cand in candidates:
        if not cand or cand in seen:
            continue
        kilo_path = Path(cand) / "kilo"
        if kilo_path.exists():
            parts.insert(0, cand)
            seen.add(cand)
            added.append(cand)

    new_path = ":".join(parts)
    kilo_resolved = _which_in_path("kilo", new_path)
    return new_path, added, kilo_resolved


def _normalize_systemd_limit_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.lower() in {"0", "off", "none"}:
        return None
    return value


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


def _missing_runs_total(cells: list[dict[str, Any]]) -> int:
    return int(sum(int(c.get("need", 0)) for c in cells))


def _split_missing_by_blocked_models(
    missing: list[dict[str, Any]], blocked_models: set[tuple[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for cell in missing:
        key = (str(cell.get("provider") or ""), str(cell.get("model_id") or ""))
        if key in blocked_models:
            deferred.append(cell)
        else:
            active.append(cell)
    return active, deferred


def _parse_created_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _blocked_models_by_recent_failures(
    *,
    db_path: Path,
    prompt_profile: str,
    prompt_strategy: str,
    mode: str,
    budget_seconds: int,
    failure_threshold: int,
    window_hours: float,
) -> tuple[set[tuple[str, str]], dict[tuple[str, str], dict[str, Any]]]:
    blocked: set[tuple[str, str]] = set()
    details: dict[tuple[str, str], dict[str, Any]] = {}
    if failure_threshold <= 0 or window_hours <= 0:
        return blocked, details
    if not db_path.exists():
        return blocked, details

    rows: list[tuple[str, str, str, str, str, str]] = []
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT provider, model_id, status, created_at, competition_id, run_id
            FROM runs
            WHERE prompt_profile=?
              AND prompt_strategy=?
              AND COALESCE(mode, '')=?
              AND budget_time_seconds=?
            """,
            (prompt_profile, prompt_strategy, mode, int(budget_seconds)),
        )
        rows = [
            (
                str(r[0] or ""),
                str(r[1] or ""),
                str(r[2] or ""),
                str(r[3] or ""),
                str(r[4] or ""),
                str(r[5] or ""),
            )
            for r in cur.fetchall()
        ]
    except sqlite3.OperationalError:
        return blocked, details
    finally:
        con.close()

    cutoff = datetime.now().astimezone() - timedelta(hours=float(window_hours))
    by_model: dict[tuple[str, str], list[tuple[datetime, str, str, str]]] = {}
    for provider, model_id, status, created_at, competition_id, run_id in rows:
        if not provider or not model_id or not status:
            continue
        dt = _parse_created_at(created_at)
        if dt is None or dt < cutoff:
            continue
        by_model.setdefault((provider, model_id), []).append((dt, status, competition_id, run_id))

    for key, recs in by_model.items():
        recs.sort(key=lambda x: x[0], reverse=True)
        consecutive_failures = 0
        for _, status, _, _ in recs:
            if status == "success":
                break
            consecutive_failures += 1

        if consecutive_failures >= int(failure_threshold):
            blocked.add(key)
            details[key] = {
                "consecutive_failures": int(consecutive_failures),
                "window_hours": float(window_hours),
                "recent": [
                    {
                        "created_at": dt.isoformat(timespec="seconds"),
                        "status": status,
                        "competition_id": competition_id,
                        "run_id": run_id,
                    }
                    for (dt, status, competition_id, run_id) in recs[:10]
                ],
            }
    return blocked, details


def _write_filtered_model_set(
    *,
    src_path: Path,
    dst_path: Path,
    blocked_models: set[tuple[str, str]],
) -> tuple[int, int]:
    raw = _load_json(src_path)
    models = raw.get("models")
    if not isinstance(models, list):
        raise ValueError(f"Invalid model set file (missing models list): {src_path}")

    kept_models: list[dict[str, Any]] = []
    total = 0
    for m in models:
        if not isinstance(m, dict):
            continue
        provider = str(m.get("provider") or "").strip()
        model_id = str(m.get("model_id") or "").strip()
        if not provider or not model_id:
            continue
        total += 1
        if (provider, model_id) in blocked_models:
            continue
        kept_models.append(m)

    obj = dict(raw)
    obj["models"] = kept_models
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return len(kept_models), int(total)


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
    if "final_deferred" in status:
        lines.append("## final_deferred")
        lines.append("```json")
        lines.append(json.dumps(status["final_deferred"], indent=2, sort_keys=True))
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
    model_circuit_breaker_enabled = bool(cfg.get("model_circuit_breaker_enabled", False))
    model_failure_threshold = int(cfg.get("model_failure_threshold", 3))
    model_failure_window_hours = float(cfg.get("model_failure_window_hours", 24))
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
        model_circuit_breaker_enabled=model_circuit_breaker_enabled,
        model_failure_threshold=model_failure_threshold,
        model_failure_window_hours=model_failure_window_hours,
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
                blocked_models: set[tuple[str, str]] = set()
                blocked_details: dict[tuple[str, str], dict[str, Any]] = {}
                if model_circuit_breaker_enabled:
                    blocked_models, blocked_details = _blocked_models_by_recent_failures(
                        db_path=db_path,
                        prompt_profile=profile,
                        prompt_strategy=prompt_strategy,
                        mode=mode,
                        budget_seconds=budget_seconds,
                        failure_threshold=model_failure_threshold,
                        window_hours=model_failure_window_hours,
                    )

                blocked_labels = [f"{p}::{m}" for (p, m) in sorted(blocked_models)]
                attempt_models_path = models_path
                kept_models = len(models)
                total_models = len(models)
                if blocked_models:
                    attempt_models_path = run_dir / "tmp_models" / f"{profile}_attempt{attempt}.json"
                    kept_models, total_models = _write_filtered_model_set(
                        src_path=models_path,
                        dst_path=attempt_models_path,
                        blocked_models=blocked_models,
                    )
                    print(
                        f"[{_now_iso()}] model circuit-breaker: blocked_models={len(blocked_models)} "
                        f"kept_models={kept_models}/{total_models} "
                        f"(threshold={model_failure_threshold} failures, window={model_failure_window_hours}h)"
                    )
                    for provider, model_id in sorted(blocked_models):
                        label = f"{provider}::{model_id}"
                        detail = blocked_details.get((provider, model_id), {})
                        streak = int(detail.get("consecutive_failures", 0))
                        print(f"  - blocked: {label} (consecutive_failures={streak})")
                    sys.stdout.flush()
                    _append_event(
                        run_dir,
                        "model_circuit_breaker",
                        profile=profile,
                        attempt=attempt,
                        threshold=model_failure_threshold,
                        window_hours=model_failure_window_hours,
                        blocked_models=blocked_labels,
                        blocked_details=[
                            {
                                "provider": p,
                                "model_id": m,
                                **blocked_details.get((p, m), {}),
                            }
                            for (p, m) in sorted(blocked_models)
                        ],
                    )

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
                    str(attempt_models_path),
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

                if kept_models <= 0:
                    rc = 0
                    _append_event(
                        run_dir,
                        "profile_attempt_skipped",
                        profile=profile,
                        attempt=attempt,
                        reason="all_models_blocked_by_circuit_breaker",
                    )
                    print(
                        f"[{_now_iso()}] profile={profile} attempt={attempt} skipped: "
                        "all models blocked by circuit-breaker"
                    )
                    sys.stdout.flush()
                else:
                    proc = subprocess.run(cmd, cwd=repo_root)
                    rc = int(proc.returncode)
                rc_kind = "exit_code" if rc >= 0 else "signal"
                rc_value = rc if rc >= 0 else (-rc)

                missing_all, missing_runs_all = _missing_cells(
                    db_path=db_path,
                    competitions=competitions,
                    models=models,
                    runs_per_model=runs_per_model,
                    prompt_profile=profile,
                    prompt_strategy=prompt_strategy,
                    mode=mode,
                    budget_seconds=budget_seconds,
                )
                missing_active, deferred_missing = _split_missing_by_blocked_models(
                    missing_all, blocked_models
                )
                missing_runs = _missing_runs_total(missing_active)
                deferred_runs = _missing_runs_total(deferred_missing)
                summary = {
                    "attempt": attempt,
                    "finished_at": _now_iso(),
                    "returncode": rc,
                    "return_kind": rc_kind,
                    "return_value": rc_value,
                    "missing_cells": len(missing_active),
                    "missing_runs": missing_runs,
                    "missing_cells_total": len(missing_all),
                    "missing_runs_total": int(missing_runs_all),
                    "deferred_cells": len(deferred_missing),
                    "deferred_runs": deferred_runs,
                    "blocked_models": blocked_labels,
                }
                attempts_log[profile].append(summary)
                _update_status(run_dir, attempts=attempts_log, latest_attempt=summary)
                _append_event(run_dir, "profile_attempt_end", profile=profile, **summary)
                print(
                    f"[{summary['finished_at']}] profile={profile} attempt={attempt} rc={rc} "
                    f"missing_cells={summary['missing_cells']} missing_runs={summary['missing_runs']} "
                    f"deferred_cells={summary['deferred_cells']} deferred_runs={summary['deferred_runs']}"
                )
                sys.stdout.flush()

                if summary["missing_cells"] == 0:
                    profile_done = True
                    _append_event(
                        run_dir,
                        "profile_complete",
                        profile=profile,
                        attempt=attempt,
                        deferred_cells=summary["deferred_cells"],
                        deferred_runs=summary["deferred_runs"],
                    )
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
        final_deferred: dict[str, dict[str, int]] = {}
        for profile in profiles:
            missing_all, missing_runs_all = _missing_cells(
                db_path=db_path,
                competitions=competitions,
                models=models,
                runs_per_model=runs_per_model,
                prompt_profile=profile,
                prompt_strategy=prompt_strategy,
                mode=mode,
                budget_seconds=int(PROFILE_BUDGET_SECONDS[profile]),
            )
            blocked_models: set[tuple[str, str]] = set()
            if model_circuit_breaker_enabled:
                blocked_models, _ = _blocked_models_by_recent_failures(
                    db_path=db_path,
                    prompt_profile=profile,
                    prompt_strategy=prompt_strategy,
                    mode=mode,
                    budget_seconds=int(PROFILE_BUDGET_SECONDS[profile]),
                    failure_threshold=model_failure_threshold,
                    window_hours=model_failure_window_hours,
                )
            missing_active, deferred_missing = _split_missing_by_blocked_models(
                missing_all, blocked_models
            )
            final_missing[profile] = {
                "missing_cells": len(missing_active),
                "missing_runs": int(_missing_runs_total(missing_active)),
            }
            final_deferred[profile] = {
                "deferred_cells": len(deferred_missing),
                "deferred_runs": int(_missing_runs_total(deferred_missing)),
                "missing_cells_total": len(missing_all),
                "missing_runs_total": int(missing_runs_all),
            }

        _update_status(
            run_dir,
            state="completed" if final_exit == 0 else "failed",
            finished_at=_now_iso(),
            current_profile=None,
            current_attempt=None,
            final_missing=final_missing,
            final_deferred=final_deferred,
            exit_code=final_exit,
        )
        _append_event(
            run_dir,
            "worker_complete",
            exit_code=final_exit,
            final_missing=final_missing,
            final_deferred=final_deferred,
        )
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


def _launch_with_systemd(
    *,
    repo_root: Path,
    run_dir: Path,
    run_name: str,
    log_path: Path,
    memory_high: str | None,
    memory_max: str | None,
    auto_resume_on_abort: bool,
    restart_sec: float,
) -> dict[str, Any]:
    unit = f"tmlbench_async_{run_name.replace('-', '_').replace('.', '_')}"
    env_overrides: dict[str, str] = {}
    for key in ("PATH", "HOME", "PYENV_ROOT", "NVM_DIR", "NVM_BIN", "XDG_RUNTIME_DIR", "PYTHONUNBUFFERED"):
        val = os.environ.get(key)
        if val:
            env_overrides[key] = val
    if "PYTHONUNBUFFERED" not in env_overrides:
        env_overrides["PYTHONUNBUFFERED"] = "1"
    base_path = env_overrides.get("PATH") or os.environ.get("PATH") or os.defpath
    augmented_path, kilo_path_added, kilo_resolved = _augment_path_for_kilo(
        path_value=base_path,
        home=env_overrides.get("HOME") or os.environ.get("HOME"),
        nvm_dir=env_overrides.get("NVM_DIR") or os.environ.get("NVM_DIR"),
        nvm_bin=env_overrides.get("NVM_BIN") or os.environ.get("NVM_BIN"),
    )
    env_overrides["PATH"] = augmented_path
    if kilo_resolved is None:
        raise RuntimeError(
            "Cannot resolve `kilo` from launch PATH. "
            "Set PATH/NVM_DIR/NVM_BIN (or install kilo) before starting async run."
        )
    runner_cmd = (
        f"cd {shlex.quote(str(repo_root))} && "
        f"exec {shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} run "
        f"--run-dir {shlex.quote(str(run_dir))} >> {shlex.quote(str(log_path))} 2>&1"
    )
    restart_delay = max(0.0, float(restart_sec))
    service_props = ["OOMPolicy=continue"]
    if memory_high:
        service_props.append(f"MemoryHigh={memory_high}")
    if memory_max:
        service_props.append(f"MemoryMax={memory_max}")
    if auto_resume_on_abort:
        service_props.extend(
            [
                "Restart=on-failure",
                f"RestartSec={restart_delay:g}s",
                "RestartPreventExitStatus=1 2",
            ]
        )
    else:
        service_props.append("Restart=no")

    cmd = [
        "systemd-run",
        "--user",
        "--unit",
        unit,
    ]
    for prop in service_props:
        cmd.extend(["--property", prop])
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
        kilo_path=kilo_resolved,
        kilo_path_added=kilo_path_added,
        memory_high=memory_high,
        memory_max=memory_max,
        auto_resume_on_abort=auto_resume_on_abort,
        restart_sec=restart_delay,
        stdout=proc.stdout.strip(),
    )
    return {
        "method": "systemd",
        "unit": unit,
        "env_keys": sorted(env_overrides.keys()),
        "kilo_path": kilo_resolved,
        "kilo_path_added": kilo_path_added,
        "memory_high": memory_high,
        "memory_max": memory_max,
        "auto_resume_on_abort": auto_resume_on_abort,
        "restart_sec": restart_delay,
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
    restart_sec = float(args.restart_sec)
    if restart_sec < 0:
        raise SystemExit("--restart-sec must be >= 0")

    systemd_memory_high = _normalize_systemd_limit_value(args.systemd_memory_high)
    systemd_memory_max = _normalize_systemd_limit_value(args.systemd_memory_max)
    auto_resume_on_abort = not bool(args.disable_auto_resume_on_abort)

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
        "model_circuit_breaker_enabled": not bool(args.disable_model_circuit_breaker),
        "model_failure_threshold": int(args.model_failure_threshold),
        "model_failure_window_hours": float(args.model_failure_window_hours),
        "systemd_memory_high": systemd_memory_high,
        "systemd_memory_max": systemd_memory_max,
        "auto_resume_on_abort": auto_resume_on_abort,
        "restart_sec": restart_sec,
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
        launch_meta = _launch_with_systemd(
            repo_root=repo_root,
            run_dir=run_dir,
            run_name=run_name,
            log_path=log_path,
            memory_high=systemd_memory_high,
            memory_max=systemd_memory_max,
            auto_resume_on_abort=auto_resume_on_abort,
            restart_sec=restart_sec,
        )
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
    print(f"model_circuit_breaker={cfg.get('model_circuit_breaker_enabled')}")
    print(f"model_failure_threshold={cfg.get('model_failure_threshold')}")
    print(f"model_failure_window_hours={cfg.get('model_failure_window_hours')}")
    if launch_meta.get("method") == "systemd":
        print(f"systemd_unit={launch_meta.get('unit')}")
        print(f"systemd_memory_high={launch_meta.get('memory_high')}")
        print(f"systemd_memory_max={launch_meta.get('memory_max')}")
        print(f"auto_resume_on_abort={launch_meta.get('auto_resume_on_abort')}")
        print(f"restart_sec={launch_meta.get('restart_sec')}")
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
    if "final_deferred" in status:
        print(f"final_deferred={json.dumps(status['final_deferred'], sort_keys=True)}")
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
    ap_start.add_argument(
        "--model-failure-threshold",
        type=int,
        default=3,
        help="Circuit-breaker threshold: block a model after this many consecutive failures in the window.",
    )
    ap_start.add_argument(
        "--model-failure-window-hours",
        type=float,
        default=24.0,
        help="Circuit-breaker lookback window in hours for model failure streak checks.",
    )
    ap_start.add_argument(
        "--disable-model-circuit-breaker",
        action="store_true",
        help="Disable model-level failure circuit breaker for this run.",
    )
    ap_start.add_argument("--resume-any-status", action="store_true")
    ap_start.add_argument("--launch-method", default="auto", help="auto|systemd|popen (default: auto)")
    ap_start.add_argument(
        "--systemd-memory-high",
        default="16G",
        help="systemd MemoryHigh for run unit; use 0/off/none to disable.",
    )
    ap_start.add_argument(
        "--systemd-memory-max",
        default="22G",
        help="systemd MemoryMax for run unit; use 0/off/none to disable.",
    )
    ap_start.add_argument(
        "--disable-auto-resume-on-abort",
        action="store_true",
        help="Disable systemd auto-restart for unexpected run aborts/failures.",
    )
    ap_start.add_argument(
        "--restart-sec",
        type=float,
        default=30.0,
        help="Delay (seconds) before systemd restart when auto-resume is enabled.",
    )
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
