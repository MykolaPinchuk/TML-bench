from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


def _pacific_tz_name() -> str:
    return "America/Los_Angeles"


def _get_pacific_tz():
    try:
        from zoneinfo import ZoneInfo  # type: ignore

        return ZoneInfo(_pacific_tz_name())
    except Exception:
        return None


def _now_iso() -> str:
    tz = _get_pacific_tz()
    now = datetime.now(tz) if tz is not None else datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat()


def _parse_iso(s: str) -> datetime:
    # Accept `...+00:00` or `...Z` if ever used.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@dataclass(frozen=True)
class RunState:
    created_at: str
    started_at: str | None
    time_budget_seconds: int
    provider: str | None = None
    model_id: str | None = None
    mode: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    prompt_profile: str | None = None
    prompt_strategy: str | None = None

    def elapsed_seconds(self, *, now: datetime | None = None) -> float:
        if self.started_at is None:
            raise ValueError("run_state.started_at is not set; start the timer first")
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
        started_at=raw.get("started_at"),
        time_budget_seconds=int(raw["time_budget_seconds"]),
        provider=raw.get("provider"),
        model_id=raw.get("model_id"),
        mode=raw.get("mode"),
        temperature=raw.get("temperature"),
        max_tokens=raw.get("max_tokens"),
        prompt_profile=raw.get("prompt_profile"),
        prompt_strategy=raw.get("prompt_strategy"),
    )


def init_run_state(*, run_dir: Path, time_budget_seconds: int) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_state.json"
    state = RunState(created_at=_now_iso(), started_at=None, time_budget_seconds=time_budget_seconds)
    write_run_state(state_path, state)
    return state_path


def set_run_metadata(
    state: RunState,
    *,
    provider: str | None,
    model_id: str | None,
    mode: str | None,
    temperature: float | None,
    max_tokens: int | None,
    prompt_profile: str | None,
    prompt_strategy: str | None,
) -> RunState:
    return replace(
        state,
        provider=provider if provider is not None else state.provider,
        model_id=model_id if model_id is not None else state.model_id,
        mode=mode if mode is not None else state.mode,
        temperature=temperature if temperature is not None else state.temperature,
        max_tokens=max_tokens if max_tokens is not None else state.max_tokens,
        prompt_profile=prompt_profile if prompt_profile is not None else state.prompt_profile,
        prompt_strategy=prompt_strategy if prompt_strategy is not None else state.prompt_strategy,
    )


def start_timer(state: RunState) -> RunState:
    return replace(state, started_at=_now_iso())
