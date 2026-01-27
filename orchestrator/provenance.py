from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def public_manifest(*, public_dir: Path) -> tuple[dict[str, Any], str]:
    files: list[dict[str, Any]] = []
    for p in sorted(public_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(public_dir).as_posix()
        files.append({"path": rel, "bytes": int(p.stat().st_size), "sha256": sha256_file(p)})
    manifest: dict[str, Any] = {"files": files}
    return manifest, sha256_bytes(_stable_json_bytes(manifest))


def kilo_version(*, timeout_seconds: int = 2) -> str | None:
    cmds = [
        ["kilo", "--version"],
        ["kilo", "version"],
        ["kilo", "-V"],
    ]
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout_seconds).strip()
        except Exception:  # noqa: BLE001
            continue
        if out:
            return out.splitlines()[0].strip()
    return None


def _redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            kl = key.lower()
            if any(tok in kl for tok in ["apikey", "api_key", "token", "secret", "password", "key"]):
                out[key] = "<redacted>"
            else:
                out[key] = _redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [_redact_secrets(x) for x in obj]
    return obj


@dataclass(frozen=True)
class KiloConfigHash:
    config_path: str
    sha256: str


def kilo_config_hash(*, config_path: Path | None = None) -> KiloConfigHash | None:
    cfg = config_path
    if cfg is None:
        env = os.environ.get("KILO_CONFIG_PATH")
        cfg = Path(env).expanduser() if env else (Path.home() / ".kilocode" / "cli" / "config.json")
    if not cfg.exists():
        return None
    try:
        raw = json.loads(cfg.read_text(encoding="utf-8", errors="replace"))
        redacted = _redact_secrets(raw)
        digest = sha256_bytes(_stable_json_bytes(redacted))
    except Exception:  # noqa: BLE001
        # Hashing raw bytes still doesn't leak secrets; it only allows equality checks.
        digest = sha256_file(cfg)
    return KiloConfigHash(config_path=str(cfg), sha256=digest)

