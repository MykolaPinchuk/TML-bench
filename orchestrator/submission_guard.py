from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from orchestrator.schemas import CompetitionSpec
from orchestrator.validate import validate_and_normalize_submission


@dataclass(frozen=True)
class GuardStats:
    valid_snapshots: int
    last_valid_path: str | None
    last_valid_normalized_path: str | None


class SubmissionGuard:
    """
    Best-effort safety net for long headless runs.

    Watches `workspace/submission.csv` and keeps a copy of the latest *valid* submission
    (according to the public validation rules) under `artifacts/`.

    This is deliberately NOT a score-based chooser (no private holdout oracle).
    It only prevents catastrophic "final file is missing/invalid" outcomes when a run
    briefly had a valid submission earlier.
    """

    def __init__(
        self,
        *,
        spec: CompetitionSpec,
        public_dir: Path,
        workspace_dir: Path,
        artifacts_dir: Path,
        poll_interval_seconds: float = 0.25,
        stable_seconds: float = 0.4,
    ) -> None:
        self._spec = spec
        self._public_dir = public_dir
        self._workspace_dir = workspace_dir
        self._artifacts_dir = artifacts_dir
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._stable_seconds = float(stable_seconds)

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._lock = threading.Lock()
        self._valid_snapshots = 0
        self._last_valid: Path | None = None
        self._last_valid_norm: Path | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="SubmissionGuard", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def stats(self) -> GuardStats:
        with self._lock:
            return GuardStats(
                valid_snapshots=int(self._valid_snapshots),
                last_valid_path=str(self._last_valid) if self._last_valid is not None else None,
                last_valid_normalized_path=str(self._last_valid_norm) if self._last_valid_norm is not None else None,
            )

    def last_valid_submission_path(self) -> Path | None:
        with self._lock:
            return self._last_valid

    def ensure_workspace_has_valid_submission(self) -> bool:
        """
        If `workspace/submission.csv` is missing/invalid, restore the last known valid
        snapshot (if any) back into the workspace root.
        """
        src = self.last_valid_submission_path()
        if src is None or not src.exists():
            return False
        dst = self._workspace_dir / "submission.csv"
        if dst.exists():
            tmp_norm = self._artifacts_dir / "submission.guard.finalcheck.normalized.csv"
            try:
                vr = validate_and_normalize_submission(
                    spec=self._spec,
                    public_dir=self._public_dir,
                    submission_csv=dst,
                    normalized_out_csv=tmp_norm,
                )
                if vr.ok:
                    return True
            except Exception:
                pass
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return True

    def _run(self) -> None:
        submission = self._workspace_dir / "submission.csv"
        last_seen_sig: tuple[int, int] | None = None  # (mtime_ns, size)
        last_changed_at: float | None = None
        while not self._stop.is_set():
            if not submission.exists():
                time.sleep(self._poll_interval_seconds)
                continue

            try:
                st = submission.stat()
                sig = (int(st.st_mtime_ns), int(st.st_size))
            except Exception:
                time.sleep(self._poll_interval_seconds)
                continue

            now = time.monotonic()
            if last_seen_sig != sig:
                last_seen_sig = sig
                last_changed_at = now
                time.sleep(self._poll_interval_seconds)
                continue

            if last_changed_at is None or (now - last_changed_at) < self._stable_seconds:
                time.sleep(self._poll_interval_seconds)
                continue

            # Snapshot and validate.
            try:
                self._artifacts_dir.mkdir(parents=True, exist_ok=True)
                snap = self._artifacts_dir / "submission.guard.candidate.csv"
                snap_norm = self._artifacts_dir / "submission.guard.candidate.normalized.csv"
                shutil.copyfile(submission, snap)
                vr = validate_and_normalize_submission(
                    spec=self._spec,
                    public_dir=self._public_dir,
                    submission_csv=snap,
                    normalized_out_csv=snap_norm,
                )
                if not vr.ok:
                    time.sleep(self._poll_interval_seconds)
                    continue

                final = self._artifacts_dir / "submission.last_valid.csv"
                final_norm = self._artifacts_dir / "submission.last_valid.normalized.csv"
                shutil.copyfile(snap, final)
                shutil.copyfile(snap_norm, final_norm)

                with self._lock:
                    self._valid_snapshots += 1
                    self._last_valid = final
                    self._last_valid_norm = final_norm
            except Exception:
                # Ignore transient parse/write errors and keep watching.
                pass

            time.sleep(self._poll_interval_seconds)

