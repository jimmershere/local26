"""Read-only state probes (pyinfra-style facts).

Facts observe target state without changing it. The ops layer consumes these
typed snapshots and diffs them against a desired intent to decide whether any
commands need to run.
"""

from __future__ import annotations

from .models import CommandProbe, DirState, FileState, PackageState, ServiceState
from .probes import (
    command_probe,
    dir_state,
    file_state,
    package_state,
    parse_dir_state,
    parse_file_state,
    parse_package_state,
    parse_service_state,
    service_state,
)

__all__ = [
    "CommandProbe",
    "DirState",
    "FileState",
    "PackageState",
    "ServiceState",
    "command_probe",
    "dir_state",
    "file_state",
    "package_state",
    "parse_dir_state",
    "parse_file_state",
    "parse_package_state",
    "parse_service_state",
    "service_state",
]
