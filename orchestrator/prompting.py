from __future__ import annotations

from pathlib import Path


def render_prompt(
    *,
    base_prompt_path: Path,
    override_path: Path | None,
    profile_path: Path | None,
    time_budget_seconds: int,
) -> str:
    base = base_prompt_path.read_text(encoding="utf-8")
    override = override_path.read_text(encoding="utf-8") if override_path and override_path.exists() else ""
    profile = profile_path.read_text(encoding="utf-8") if profile_path and profile_path.exists() else ""
    # Allow profiles/overrides to be budget-aware too.
    token = "{{time_budget_seconds}}"
    budget = str(int(time_budget_seconds))
    base = base.replace(token, budget)
    profile = profile.replace(token, budget)
    override = override.replace(token, budget)

    rendered = base
    if profile.strip():
        rendered = rendered.rstrip() + "\n\n" + profile.strip() + "\n"
    if override.strip():
        rendered = rendered.rstrip() + "\n\n" + override.strip() + "\n"
    return rendered
