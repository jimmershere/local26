from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def profiles_dir(root: str | Path = ".") -> Path:
    return Path(root) / ".local81" / "profiles"


def list_profiles(root: str | Path = ".") -> list[str]:
    base = profiles_dir(root)
    if not base.exists():
        return []
    return sorted(path.stem for path in base.glob("*.yaml") if path.is_file())


def load_profile_data(name: str, *, root: str | Path = ".") -> dict[str, Any]:
    path = profiles_dir(root) / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"profile file must contain a mapping: {path}")
    return data


def merge_profile(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "scopes":
            merged[key] = _merge_scopes(base.get(key, {}), value)
        elif isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_profile(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_scopes(base_scopes: Any, override_scopes: Any) -> dict[str, Any]:
    base_map = dict(base_scopes or {})
    if isinstance(override_scopes, list):
        override_map = {item["name"]: {k: v for k, v in item.items() if k != "name"} for item in override_scopes}
    else:
        override_map = dict(override_scopes or {})
    for name, values in override_map.items():
        current = dict(base_map.get(name, {}))
        if isinstance(values, dict):
            current.update(values)
        else:
            current = values
        base_map[name] = current
    return base_map


def scaffold_profile(name: str) -> str:
    return (
        "local81:\n"
        f"  profile: {name}\n"
        "defaults:\n"
        "  rsync_opts: -az\n"
        "notifications:\n"
        "  notify_on_success: false\n"
        "scopes: {}\n"
    )
