from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.suite import _load_suite


def test_load_suite_ok(tmp_path: Path) -> None:
    p = tmp_path / "suite.json"
    p.write_text(
        json.dumps({"name": "x", "competitions": ["a", "b"]}, indent=2),
        encoding="utf-8",
    )
    name, comps = _load_suite(p)
    assert name == "x"
    assert comps == ["a", "b"]


def test_load_suite_missing_competitions(tmp_path: Path) -> None:
    p = tmp_path / "suite.json"
    p.write_text(json.dumps({"name": "x"}), encoding="utf-8")
    with pytest.raises(ValueError):
        _load_suite(p)


def test_load_suite_invalid_competition_id(tmp_path: Path) -> None:
    p = tmp_path / "suite.json"
    p.write_text(json.dumps({"competitions": ["ok", " "]}), encoding="utf-8")
    with pytest.raises(ValueError):
        _load_suite(p)

