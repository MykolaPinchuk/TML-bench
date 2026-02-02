from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from orchestrator.kilo_cli import run_kilo


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sanitize_filename(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s[:150] if len(s) > 150 else s


def _load_model_set(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    models = raw.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError(f"Invalid model set file (missing models list): {path}")
    out: list[dict] = []
    for i, m in enumerate(models):
        if not isinstance(m, dict):
            raise TypeError(f"Invalid model entry at index {i} in {path}: expected object")
        provider = m.get("provider")
        model_id = m.get("model_id")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(f"Invalid model entry at index {i} in {path}: missing provider")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"Invalid model entry at index {i} in {path}: missing model_id")
        out.append(
            {
                "provider": provider.strip(),
                "model_id": model_id.strip(),
                "label": str(m.get("label") or ""),
            }
        )
    return out


@dataclass(frozen=True)
class PreflightResult:
    provider: str
    model_id: str
    status: str
    returncode: int
    stop_reason: str | None
    duration_seconds: float
    workspace_dir: Path


def preflight_one(
    *,
    provider: str,
    model_id: str,
    base_dir: Path,
    timeout_seconds: int = 90,
) -> PreflightResult:
    provider = str(provider).strip()
    model_id = str(model_id).strip()
    ws = base_dir / f"{_sanitize_filename(provider)}__{_sanitize_filename(model_id)}"
    ws.mkdir(parents=True, exist_ok=True)

    sentinel = ws / "_PREFLIGHT_OK"
    try:
        if sentinel.exists():
            sentinel.unlink()
    except Exception:
        pass

    stdout_path = ws / "kilo_stdout.jsonl"
    stderr_path = ws / "kilo_stderr.log"

    prompt = (
        "Preflight check. Do NOT train a model.\n"
        "Do exactly these commands (no explanation):\n"
        "1) touch _PREFLIGHT_OK\n"
        "2) ls -la\n"
        "Then stop.\n"
    )
    kr = run_kilo(
        workspace_dir=ws,
        prompt=prompt,
        provider_id=provider,
        model_id=model_id,
        timeout_seconds=int(timeout_seconds),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stop_when_submission_path=sentinel,
        stop_on_api_402=True,
    )

    if kr.stop_reason == "api_402":
        status = "provider_error"
    elif sentinel.exists():
        status = "ok"
    elif kr.returncode == 124:
        status = "timeout"
    else:
        status = "error"

    return PreflightResult(
        provider=provider,
        model_id=model_id,
        status=status,
        returncode=int(kr.returncode),
        stop_reason=kr.stop_reason,
        duration_seconds=float(kr.duration_seconds),
        workspace_dir=ws,
    )


def _write_model_set(*, src_path: Path, dst_path: Path, models: list[dict]) -> None:
    raw = json.loads(src_path.read_text(encoding="utf-8"))
    raw["models"] = models
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(raw, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Quick provider/model preflight (tool-call check) via Kilo CLI.")
    ap.add_argument(
        "--models-path",
        default=str(_repo_root() / "orchestrator" / "model_sets" / "v3_fast.json"),
        help="JSON file with provider/model_id entries.",
    )
    ap.add_argument("--only-provider", default=None, help="If set, only preflight models from this provider id.")
    ap.add_argument("--max-models", type=int, default=None, help="If set, only preflight the first N models selected.")
    ap.add_argument("--timeout-seconds", type=int, default=90)
    ap.add_argument(
        "--out-models-path",
        default=None,
        help="If set, write a filtered model set JSON containing only models that passed preflight.",
    )
    ap.add_argument("--fail-fast", action="store_true", help="Exit non-zero if any model fails preflight.")
    args = ap.parse_args()

    model_set_path = Path(args.models_path)
    models = _load_model_set(model_set_path)
    if args.only_provider:
        models = [m for m in models if m["provider"] == args.only_provider]
    if args.max_models is not None:
        if args.max_models < 0:
            raise ValueError("--max-models must be >= 0")
        models = models[: args.max_models]
    if not models:
        raise ValueError("No models selected.")

    base_dir = _repo_root() / "tmp" / "preflight"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"models: {len(models)} from {model_set_path}")
    print(f"timeout_seconds: {int(args.timeout_seconds)}")
    print(f"workspace_base: {base_dir}")

    results: list[PreflightResult] = []
    failures = 0
    for i, m in enumerate(models, start=1):
        provider = m["provider"]
        model_id = m["model_id"]
        print(f"\n[{i}/{len(models)}] {provider} :: {model_id}")
        r = preflight_one(
            provider=provider,
            model_id=model_id,
            base_dir=base_dir,
            timeout_seconds=int(args.timeout_seconds),
        )
        results.append(r)
        print(
            f"status={r.status} rc={r.returncode} stop_reason={r.stop_reason} "
            f"dur={r.duration_seconds:.1f}s workspace={r.workspace_dir}"
        )
        if r.status != "ok":
            failures += 1
            if args.fail_fast:
                break

    ok_models: list[dict] = []
    bad_models: list[dict] = []
    ok_keys = {(r.provider, r.model_id) for r in results if r.status == "ok"}
    for m in models:
        (ok_models if (m["provider"], m["model_id"]) in ok_keys else bad_models).append(m)

    print(f"\npassed: {len(ok_models)}  failed: {len(bad_models)}")
    if bad_models:
        for m in bad_models:
            print(f"- FAIL: {m['provider']} :: {m['model_id']}")

    if args.out_models_path:
        out_path = Path(args.out_models_path)
        _write_model_set(src_path=model_set_path, dst_path=out_path, models=ok_models)
        print(f"wrote filtered model set: {out_path}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
