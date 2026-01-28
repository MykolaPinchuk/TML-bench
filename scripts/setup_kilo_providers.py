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
    openrouter_api_key: str | None
    openrouter_base_url: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_provider_keys(path: Path) -> ProviderKeys:
    if not path.exists():
        raise FileNotFoundError(f"Missing keys file: {path}")

    chutes_api_key: str | None = None
    nanogpt_api_key: str | None = None
    nanogpt_base_url: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None

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
        elif key in {"openrouter", "openrouter_api_key", "openrouter-key", "openrouter_key"}:
            openrouter_api_key = value
        elif key in {"openrouter_base_url", "openrouter_base"}:
            openrouter_base_url = value

    return ProviderKeys(
        chutes_api_key=chutes_api_key,
        nanogpt_api_key=nanogpt_api_key,
        nanogpt_base_url=nanogpt_base_url,
        openrouter_api_key=openrouter_api_key,
        openrouter_base_url=openrouter_base_url,
    )


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


def _upsert_kilocode_defaults(providers: list[dict], *, fallback_model: str) -> None:
    """
    Kilo CLI config typically includes a built-in `default` provider (type `kilocode`).
    Some older defaults reference model ids that may no longer exist upstream.

    To avoid hard failures during headless runs, keep a sane, currently-available model configured.
    """
    for p in providers:
        if not isinstance(p, dict):
            continue
        if p.get("id") != "default":
            continue
        if p.get("provider") != "kilocode":
            continue
        # Only change when missing or clearly stale.
        m = str(p.get("kilocodeModel") or "").strip()
        if (not m) or (m == "mistralai/devstral-2512:free"):
            p["kilocodeModel"] = fallback_model
        return


def _remove_provider(providers: list[dict], *, provider_id: str) -> bool:
    before = len(providers)
    providers[:] = [p for p in providers if not (isinstance(p, dict) and p.get("id") == provider_id)]
    return len(providers) != before


def _maybe_fix_global_state_for_headless_runs(*, preferred_config_name: str, preferred_provider: str, preferred_model_id: str) -> bool:
    """
    Kilo maintains a separate global state file which can override the active provider/model
    during startup (e.g., session title generation). If it points at a retired model, headless
    runs may stall until timeout even when --provider/--model are passed.
    """
    global_state_path = Path.home() / ".kilocode" / "cli" / "global" / "global-state.json"
    if not global_state_path.exists():
        return False

    state = _load_json(global_state_path)
    if not isinstance(state, dict):
        return False

    changed = False

    list_meta = state.get("listApiConfigMeta")
    openrouter_meta: dict | None = None
    if isinstance(list_meta, list):
        for item in list_meta:
            if isinstance(item, dict) and item.get("name") == preferred_config_name:
                openrouter_meta = item
                break

    if openrouter_meta is not None:
        # Ensure the meta entry is usable.
        if openrouter_meta.get("apiProvider") != preferred_provider:
            openrouter_meta["apiProvider"] = preferred_provider
            changed = True
        if openrouter_meta.get("modelId") != preferred_model_id:
            openrouter_meta["modelId"] = preferred_model_id
            changed = True

        # Prefer the specified config during startup to avoid retry loops.
        if state.get("currentApiConfigName") != preferred_config_name:
            state["currentApiConfigName"] = preferred_config_name
            changed = True
        if state.get("apiProvider") != preferred_provider:
            state["apiProvider"] = preferred_provider
            changed = True

    # If the stale model is present, replace it with something valid to avoid startup failures.
    stale = {"mistralai/devstral-2512:free", "devstral-2512:free"}
    if str(state.get("kilocodeModel") or "").strip() in stale and state.get("kilocodeModel") != preferred_model_id:
        state["kilocodeModel"] = preferred_model_id
        changed = True

    if not changed:
        return False

    _save_json(global_state_path, state)
    return True


def _maybe_update_global_state_meta(*, config_name: str, api_provider: str, model_id: str) -> bool:
    """
    Update a named entry in global-state's listApiConfigMeta without changing the active config.
    Useful to prevent retired/undesired model ids from being used if a user switches configs later.
    """
    global_state_path = Path.home() / ".kilocode" / "cli" / "global" / "global-state.json"
    if not global_state_path.exists():
        return False

    state = _load_json(global_state_path)
    if not isinstance(state, dict):
        return False

    list_meta = state.get("listApiConfigMeta")
    if not isinstance(list_meta, list):
        return False

    changed = False
    for item in list_meta:
        if not isinstance(item, dict):
            continue
        if item.get("name") != config_name:
            continue
        if item.get("apiProvider") != api_provider:
            item["apiProvider"] = api_provider
            changed = True
        if item.get("modelId") != model_id:
            item["modelId"] = model_id
            changed = True
        break

    if not changed:
        return False
    _save_json(global_state_path, state)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Configure Kilo CLI providers (Chutes + Nano-GPT + OpenRouter) from repo secrets.")
    ap.add_argument(
        "--keys-file",
        default=str(_repo_root() / "secrets" / "provider_apis.txt"),
        help="Path to a file with lines like 'chutes: <key>', 'nanogpt: <key>', and/or 'openrouter: <key>'.",
    )
    ap.add_argument(
        "--config-path",
        default=str(Path.home() / ".kilocode" / "cli" / "config.json"),
        help="Path to Kilo CLI config.json.",
    )
    ap.add_argument(
        "--set-default-provider",
        choices=["keep", "chutes", "nanogpt", "openrouter"],
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
    if not (keys.chutes_api_key or keys.nanogpt_api_key or keys.openrouter_api_key):
        raise RuntimeError(
            f"No provider keys found in {args.keys_file}. Add at least one of: chutes, nanogpt, openrouter."
        )

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

    if keys.chutes_api_key:
        _upsert_provider(
            providers,
            provider_id="chutes",
            provider_type="chutes",
            updates={
                "chutesApiKey": keys.chutes_api_key,
                # Required by Kilo's selected-provider validation; the benchmark always passes --model anyway.
                "apiModelId": "microsoft/Phi-3.5-mini-instruct",
            },
        )

    if keys.nanogpt_api_key and keys.nanogpt_base_url:
        _upsert_provider(
            providers,
            provider_id="nanogpt",
            provider_type="openai",
            updates={
                "openAiApiKey": keys.nanogpt_api_key,
                "openAiBaseUrl": keys.nanogpt_base_url,
                # Not required, but helps avoid confusion when calling Kilo without --model.
                "openAiModelId": "mistralai/devstral-2-123b-instruct-2512",
            },
        )
    elif keys.nanogpt_api_key and not keys.nanogpt_base_url:
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

    if keys.openrouter_api_key:
        base_url = keys.openrouter_base_url or "https://openrouter.ai/api/v1"
        preferred_openrouter_model = "x-ai/grok-4.1-fast"
        _upsert_provider(
            providers,
            provider_id="openrouter",
            provider_type="openai",
            updates={
                "openAiApiKey": keys.openrouter_api_key,
                "openAiBaseUrl": base_url,
                # Used by Kilo for startup checks / internal calls when no --model is passed.
                "openAiModelId": preferred_openrouter_model,
            },
        )
        # Keep Kilo's built-in `default` provider on a known-good model to avoid invalid_model errors.
        # NOTE: This is only used for Kilo's internal defaults; benchmark runs always pass --provider/--model.
        _upsert_kilocode_defaults(providers, fallback_model=preferred_openrouter_model)

    if args.set_default_provider != "keep":
        config["provider"] = str(args.set_default_provider)

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
    # Keep global-state aligned with the chosen default provider to avoid startup requests
    # going to an unexpected provider/model (which can cause retry loops and timeouts).
    preferred = None
    if args.set_default_provider == "chutes":
        preferred = ("chutes", "chutes", "microsoft/Phi-3.5-mini-instruct")
    elif args.set_default_provider == "nanogpt" and keys.nanogpt_api_key and keys.nanogpt_base_url:
        preferred = ("nanogpt", "openai", "mistralai/devstral-2-123b-instruct-2512")
    elif args.set_default_provider == "openrouter" and keys.openrouter_api_key:
        preferred = ("openrouter", "openai", "x-ai/grok-4.1-fast")
    if preferred is not None:
        fixed = _maybe_fix_global_state_for_headless_runs(
            preferred_config_name=preferred[0],
            preferred_provider=preferred[1],
            preferred_model_id=preferred[2],
        )
        if fixed:
            print("updated: ~/.kilocode/cli/global/global-state.json (avoid stale default model)")

    # Prevent accidental use of Gemini Flash if OpenRouter is configured but credits are exhausted.
    if keys.openrouter_api_key:
        _maybe_update_global_state_meta(config_name="openrouter", api_provider="openai", model_id="grok-4.1-fast")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
