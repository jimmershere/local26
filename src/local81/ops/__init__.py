"""Desired-state operations (pyinfra-style ops).

Facts observe; ops decide. Each operation is a pure ``diff(fact, intent)`` that
emits the commands needed to converge the target toward the intent. Applying a
converged plan again yields ``action=none`` everywhere, which is the property
the convergence tests assert.
"""

from __future__ import annotations

from .models import (
    ACTION_CREATE,
    ACTION_NONE,
    ACTION_UPDATE,
    Command,
    CommandIntent,
    DirIntent,
    FileIntent,
    OpResult,
    PackageIntent,
    ServiceIntent,
)
from .operations import (
    command_run,
    command_run_idempotent,
    dir_present,
    dir_present_idempotent,
    file_synced,
    file_synced_idempotent,
    package_present,
    package_present_idempotent,
    service_running,
    service_running_idempotent,
)

__all__ = [
    "ACTION_CREATE",
    "ACTION_NONE",
    "ACTION_UPDATE",
    "Command",
    "CommandIntent",
    "DirIntent",
    "FileIntent",
    "OpResult",
    "PackageIntent",
    "ServiceIntent",
    "command_run",
    "command_run_idempotent",
    "dir_present",
    "dir_present_idempotent",
    "file_synced",
    "file_synced_idempotent",
    "package_present",
    "package_present_idempotent",
    "service_running",
    "service_running_idempotent",
]
