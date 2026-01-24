from __future__ import annotations

import json
import re
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


def run_kilo(
    *,
    workspace_dir: Path,
    prompt: str,
    provider_id: str,
    model_id: str,
    timeout_seconds: int,
    stdout_path: Path,
    stderr_path: Path,
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
        cp = subprocess.run(argv, cwd=workspace_dir, stdout=out_f, stderr=err_f, timeout=timeout_seconds + 10)
    ended = time.monotonic()
    return KiloRun(argv=argv, returncode=int(cp.returncode), duration_seconds=max(0.0, ended - started))


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

