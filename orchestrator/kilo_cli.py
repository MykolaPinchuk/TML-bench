from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


@dataclass(frozen=True)
class KiloRun:
    argv: list[str]
    returncode: int
    duration_seconds: float
    stop_reason: str | None = None


def _terminate_process_group(proc: subprocess.Popen[bytes], *, timeout_seconds: int = 10) -> None:
    if proc.poll() is not None:
        return

    pgid: int | None
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:  # noqa: BLE001
        pgid = None

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    except Exception:  # noqa: BLE001
        pass

    try:
        proc.wait(timeout=timeout_seconds)
        return
    except Exception:  # noqa: BLE001
        pass

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        else:
            proc.kill()
    except Exception:  # noqa: BLE001
        pass

    try:
        proc.wait(timeout=timeout_seconds)
    except Exception:  # noqa: BLE001
        return


def run_kilo(
    *,
    workspace_dir: Path,
    prompt: str,
    provider_id: str,
    model_id: str,
    timeout_seconds: int,
    stdout_path: Path,
    stderr_path: Path,
    stop_when_submission_path: Path | None = None,
    stop_on_api_402: bool = True,
    poll_interval_seconds: float = 0.25,
) -> KiloRun:
    argv = [
        "kilo",
        "--nosplash",
        "--auto",
        "--json",
        "--yolo",
        "--timeout",
        str(int(timeout_seconds)),
        "--workspace",
        str(workspace_dir),
        "--provider",
        provider_id,
        "--model",
        model_id,
        prompt,
    ]

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    with stdout_path.open("wb") as out_f, stderr_path.open("wb") as err_f:
        proc = subprocess.Popen(
            argv,
            cwd=workspace_dir,
            stdout=subprocess.PIPE,
            stderr=err_f,
            start_new_session=True,
        )
        if proc.stdout is None:
            raise RuntimeError("Failed to capture Kilo stdout (proc.stdout is None).")

        returncode: int | None = None
        stop_reason: str | None = None
        deadline = started + float(timeout_seconds)
        saw_submission_at: float | None = None
        scan_buf = b""

        def _drain_stdout(*, max_bytes: int | None = None) -> None:
            nonlocal scan_buf
            if proc.stdout is None:
                return
            remaining = max_bytes
            while True:
                if remaining is not None and remaining <= 0:
                    return
                r, _, _ = select.select([proc.stdout], [], [], 0.0)
                if not r:
                    return
                chunk = os.read(proc.stdout.fileno(), 4096 if remaining is None else min(4096, remaining))
                if not chunk:
                    return
                out_f.write(chunk)
                scan_buf = (scan_buf + chunk)[-65536:]
                if remaining is not None:
                    remaining -= len(chunk)

        while True:
            # Consume any available output so we can react to provider errors quickly.
            _drain_stdout()
            if stop_on_api_402 and (stop_reason is None) and (b"402 status code" in scan_buf):
                stop_reason = "api_402"
                _terminate_process_group(proc)
                returncode = int(proc.returncode or 0)
                break

            if proc.poll() is not None:
                _drain_stdout(max_bytes=None)
                returncode = int(proc.returncode or 0)
                # If Kilo timed out internally, aggressively kill the whole process group to avoid
                # leaving long-running child processes behind (e.g., `python train_model.py`).
                if returncode == 124:
                    _terminate_process_group(proc)
                break
            now = time.monotonic()
            if stop_when_submission_path is not None and stop_when_submission_path.exists():
                # Give a tiny grace window so we don't kill while the file is still being written.
                if saw_submission_at is None:
                    saw_submission_at = now
                if now - saw_submission_at >= 0.5:
                    _terminate_process_group(proc)
                    returncode = int(proc.returncode or 0)
                    break
            if now >= deadline:
                _terminate_process_group(proc)
                returncode = 124
                break
            time.sleep(max(0.05, float(poll_interval_seconds)))
    ended = time.monotonic()
    return KiloRun(
        argv=argv,
        returncode=int(returncode),
        duration_seconds=max(0.0, ended - started),
        stop_reason=stop_reason,
    )


def iter_json_events_from_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = strip_ansi(raw_line).strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def write_clean_jsonl(*, src_jsonl: Path, dst_jsonl: Path) -> int:
    dst_jsonl.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with dst_jsonl.open("w", encoding="utf-8") as f:
        for obj in iter_json_events_from_jsonl(src_jsonl):
            f.write(json.dumps(obj, sort_keys=True) + "\n")
            count += 1
    return count
