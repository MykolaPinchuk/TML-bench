#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderKeys:
    chutes_api_key: str | None
    nanogpt_api_key: str | None
    nanogpt_base_url: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_provider_keys(path: Path) -> ProviderKeys:
    if not path.exists():
        raise FileNotFoundError(f"Missing keys file: {path}")

    chutes_api_key: str | None = None
    nanogpt_api_key: str | None = None
    nanogpt_base_url: str | None = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip().lower()
        value = v.strip()
        if not value:
            continue
        if key in {"chutes", "chutes_api_key", "chutes-key", "chutes_key"}:
            chutes_api_key = value
        elif key in {"nanogpt", "nano-gpt", "nano_gpt", "nanogpt_api_key", "nanogpt-key", "nanogpt_key"}:
            nanogpt_api_key = value
        elif key in {"nanogpt_base_url", "nanogpt_base", "nano_gpt_base_url", "nano_gpt_base"}:
            nanogpt_base_url = value

    return ProviderKeys(chutes_api_key=chutes_api_key, nanogpt_api_key=nanogpt_api_key, nanogpt_base_url=nanogpt_base_url)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_provider(providers: list[dict], *, provider_id: str, provider_type: str, updates: dict) -> None:
    for p in providers:
        if p.get("id") == provider_id:
            p["provider"] = provider_type
            p.update(updates)
            return
    providers.append({"id": provider_id, "provider": provider_type, **updates})


def _remove_provider(providers: list[dict], *, provider_id: str) -> bool:
    before = len(providers)
    providers[:] = [p for p in providers if not (isinstance(p, dict) and p.get("id") == provider_id)]
    return len(providers) != before


def main() -> int:
    ap = argparse.ArgumentParser(description="Configure Kilo CLI providers (Chutes + Nano-GPT) from repo secrets.")
    ap.add_argument(
        "--keys-file",
        default=str(_repo_root() / "secrets" / "provider_apis.txt"),
        help="Path to a file with lines like 'chutes: <key>' and 'nanogpt: <key>'.",
    )
    ap.add_argument(
        "--config-path",
        default=str(Path.home() / ".kilocode" / "cli" / "config.json"),
        help="Path to Kilo CLI config.json.",
    )
    ap.add_argument(
        "--set-default-provider",
        choices=["keep", "chutes", "nanogpt"],
        default="chutes",
        help="Which provider id to set as the default for Kilo CLI invocations without --provider.",
    )
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    ap.add_argument(
        "--enable-exec",
        action="store_true",
        help="Expand Kilo CLI command allowlist for benchmark runs (enables python/pip/pytest/etc).",
    )
    args = ap.parse_args()

    keys = _load_provider_keys(Path(args.keys_file))
    if not keys.chutes_api_key:
        raise RuntimeError(f"Missing Chutes key in {args.keys_file} (expected a line like 'chutes: ...').")
    if not keys.nanogpt_api_key:
        raise RuntimeError(f"Missing Nano-GPT key in {args.keys_file} (expected a line like 'nanogpt: ...').")

    config_path = Path(args.config_path)
    config = _load_json(config_path)

    config.setdefault("version", "1.0.0")
    config.setdefault("mode", "code")
    config.setdefault("telemetry", True)
    config.setdefault("provider", "default")
    config.setdefault("providers", [])
    config.setdefault("autoApproval", {})
    if not isinstance(config["providers"], list):
        raise TypeError(f"Invalid Kilo config: providers must be a list (path: {config_path})")

    providers: list[dict] = config["providers"]

    _upsert_provider(
        providers,
        provider_id="chutes",
        provider_type="chutes",
        updates={
            "chutesApiKey": keys.chutes_api_key,
            # Required by Kilo's selected-provider validation; the benchmark always passes --model anyway.
            "apiModelId": "gpt-4o",
        },
    )
    if keys.nanogpt_base_url:
        _upsert_provider(
            providers,
            provider_id="nanogpt",
            provider_type="openai",
            updates={
                "openAiApiKey": keys.nanogpt_api_key,
                "openAiBaseUrl": keys.nanogpt_base_url,
                # Not required, but helps avoid confusion when calling Kilo without --model.
                "openAiModelId": "gpt-4o",
            },
        )
    else:
        removed = _remove_provider(providers, provider_id="nanogpt")
        if removed:
            print(
                "note: removed non-functional provider id 'nanogpt' from Kilo config; "
                f"add 'nanogpt_base_url: https://.../v1' to {args.keys_file} and rerun to enable NanoGPT via OpenAI-compatible API."
            )
        else:
            print(
                f"note: NanoGPT not configured (missing nanogpt_base_url in {args.keys_file}); "
                "add 'nanogpt_base_url: https://.../v1' and rerun to enable NanoGPT via OpenAI-compatible API."
            )

    if args.set_default_provider != "keep":
        config["provider"] = "chutes" if args.set_default_provider == "chutes" else "nanogpt"

    if args.enable_exec:
        auto = config.get("autoApproval") or {}
        if not isinstance(auto, dict):
            raise TypeError(f"Invalid Kilo config: autoApproval must be an object (path: {config_path})")
        exec_cfg = auto.get("execute") or {}
        if not isinstance(exec_cfg, dict):
            raise TypeError(f"Invalid Kilo config: autoApproval.execute must be an object (path: {config_path})")

        exec_cfg["enabled"] = True
        allowed = exec_cfg.get("allowed") or []
        if not isinstance(allowed, list):
            allowed = []
        allowed_set = {str(x) for x in allowed if isinstance(x, (str, int, float))}
        allowed_set.update(
            {
                "ls",
                "cat",
                "echo",
                "pwd",
                "head",
                "tail",
                "wc",
                "find",
                "rg",
                "mkdir",
                "cp",
                "mv",
                "python",
                "python3",
                "pip",
                "pip3",
                "pytest",
                "git",
                "bash",
                "sh",
            }
        )
        exec_cfg["allowed"] = sorted(allowed_set)
        # Keep an explicit deny list for obviously destructive commands.
        denied = exec_cfg.get("denied") or []
        if not isinstance(denied, list):
            denied = []
        denied_set = {str(x) for x in denied if isinstance(x, (str, int, float))}
        denied_set.update({"rm -rf", "sudo rm", "mkfs", "dd if="})
        exec_cfg["denied"] = sorted(denied_set)
        auto["execute"] = exec_cfg
        config["autoApproval"] = auto

    if args.dry_run:
        print(f"dry-run: would update {config_path}")
        print("providers now include ids:", sorted({p.get("id") for p in providers if isinstance(p, dict)}))
        print("default provider id:", config.get("provider"))
        return 0

    _save_json(config_path, config)
    print(f"updated: {config_path}")
    print("providers now include ids:", sorted({p.get('id') for p in providers if isinstance(p, dict)}))
    print("default provider id:", config.get("provider"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
