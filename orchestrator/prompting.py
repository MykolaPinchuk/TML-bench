from __future__ import annotations

from pathlib import Path


def render_prompt(*, base_prompt_path: Path, override_path: Path | None, time_budget_seconds: int) -> str:
    base = base_prompt_path.read_text(encoding="utf-8")
    override = override_path.read_text(encoding="utf-8") if override_path and override_path.exists() else ""
    rendered = base.replace("{{time_budget_seconds}}", str(time_budget_seconds))
    if override.strip():
        rendered = rendered.rstrip() + "\n\n" + override.strip() + "\n"
    return rendered

