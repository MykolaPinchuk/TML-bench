#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    py = sys.executable
    _run([py, "scripts/update_profiled1_fiverun_tables.py"])
    _run([py, "scripts/check_profiled1_canonical_coverage.py"])
    print("refresh_and_verify=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
