from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from orchestrator.result import new_run_id


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    workspace_dir: Path
    artifacts_dir: Path
    instructions_path: Path


def create_run_dirs(*, runs_root: Path, run_id: str) -> RunPaths:
    run_dir = runs_root / run_id
    workspace_dir = run_dir / "workspace"
    artifacts_dir = run_dir / "artifacts"
    workspace_dir.mkdir(parents=True, exist_ok=False)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    instructions_path = workspace_dir / "RUN_INSTRUCTIONS.md"
    return RunPaths(
        run_id=run_id,
        run_dir=run_dir,
        workspace_dir=workspace_dir,
        artifacts_dir=artifacts_dir,
        instructions_path=instructions_path,
    )


def copy_public_inputs(*, competition_dir: Path, workspace_dir: Path) -> None:
    src = competition_dir / "public"
    if not src.exists():
        raise FileNotFoundError(f"Missing competition public dir: {src}. Run prepare_competition.py first.")
    dst = workspace_dir / "public"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_run_instructions(*, instructions_path: Path, rendered_prompt: str) -> None:
    instructions_path.write_text(rendered_prompt.strip() + "\n", encoding="utf-8")


def default_run_id(*, competition_id: str) -> str:
    return new_run_id(prefix=competition_id)

