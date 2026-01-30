from __future__ import annotations

from pathlib import Path

from orchestrator.prompting import render_prompt


def test_render_prompt_replaces_budget_token_in_all_sections(tmp_path: Path) -> None:
    base = tmp_path / "base.md"
    prof = tmp_path / "profile.md"
    ov = tmp_path / "override.md"

    base.write_text("base {{time_budget_seconds}}", encoding="utf-8")
    prof.write_text("profile {{time_budget_seconds}}", encoding="utf-8")
    ov.write_text("override {{time_budget_seconds}}", encoding="utf-8")

    out = render_prompt(
        base_prompt_path=base,
        override_path=ov,
        profile_path=prof,
        time_budget_seconds=123,
    )
    assert "{{time_budget_seconds}}" not in out
    assert "base 123" in out
    assert "profile 123" in out
    assert "override 123" in out

