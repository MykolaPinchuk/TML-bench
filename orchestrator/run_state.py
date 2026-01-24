from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(s: str) -> datetime:
    # Accept `...+00:00` or `...Z` if ever used.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@dataclass(frozen=True)
class RunState:
    created_at: str
    started_at: str
    time_budget_seconds: int

    def elapsed_seconds(self, *, now: datetime | None = None) -> float:
        now_dt = now or datetime.now(timezone.utc)
        started = _parse_iso(self.started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return max(0.0, (now_dt - started).total_seconds())


def write_run_state(path: Path, state: RunState) -> None:
    path.write_text(json.dumps(state.__dict__, indent=2, sort_keys=True), encoding="utf-8")


def read_run_state(path: Path) -> RunState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RunState(
        created_at=str(raw["created_at"]),
        started_at=str(raw["started_at"]),
        time_budget_seconds=int(raw["time_budget_seconds"]),
    )


def init_run_state(*, run_dir: Path, time_budget_seconds: int) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_state.json"
    state = RunState(created_at=_utc_iso(), started_at=_utc_iso(), time_budget_seconds=time_budget_seconds)
    write_run_state(state_path, state)
    return state_path

