from __future__ import annotations

from typing import Any

SECRET_KEY_PARTS = ("password", "passwd", "secret", "token", "api_key", "credential")
SAFE_SECRET_SUFFIXES = ("_env", "_ref", "_file")


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith(SAFE_SECRET_SUFFIXES):
        return False
    return any(part in lowered for part in SECRET_KEY_PARTS)


def redact_value(key: str, value: Any) -> Any:
    if is_secret_key(key):
        return "<redacted>"
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


def redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in values.items()}
