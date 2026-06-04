from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


FINGERPRINT_PREFIX = "sha256:"
_SHA256_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(slots=True)
class PlanIntegrityFinding:
    level: str
    detail: str


def config_fingerprint(config_path: Path) -> str:
    return FINGERPRINT_PREFIX + hashlib.sha256(config_path.read_bytes()).hexdigest()


def is_valid_config_fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_FINGERPRINT_RE.fullmatch(value))


def plan_provenance_warnings(plan_data: dict, *, current_config_path: Path | None = None) -> list[PlanIntegrityFinding]:
    warnings: list[PlanIntegrityFinding] = []
    for key in ("local81_version", "created_at"):
        if key not in plan_data:
            warnings.append(PlanIntegrityFinding("WARN", f"plan is missing provenance key: {key}"))

    fingerprint = plan_data.get("config_fingerprint")
    if fingerprint is None:
        warnings.append(PlanIntegrityFinding("WARN", "plan is missing config_fingerprint provenance metadata"))
        return warnings
    if not is_valid_config_fingerprint(fingerprint):
        warnings.append(PlanIntegrityFinding("WARN", "plan config_fingerprint is not a sha256:<64 lowercase hex> value"))
        return warnings
    if current_config_path is not None and current_config_path.is_file():
        current_fingerprint = config_fingerprint(current_config_path)
        if fingerprint != current_fingerprint:
            warnings.append(
                PlanIntegrityFinding(
                    "WARN",
                    f"plan config_fingerprint does not match current config {current_config_path}; generate a fresh plan before deploy",
                )
            )
    return warnings
