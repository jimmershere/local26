"""Typed results returned by fact probes.

Facts are read-only observations of target state. Each dataclass is a plain,
serialisable snapshot that the ops layer diffs against a desired intent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FileState:
    path: str
    exists: bool
    is_file: bool = False
    mode: str | None = None
    owner: str | None = None
    group: str | None = None
    size: int | None = None
    sha256: str | None = None


@dataclass(slots=True, frozen=True)
class DirState:
    path: str
    exists: bool
    is_dir: bool = False
    mode: str | None = None
    owner: str | None = None
    group: str | None = None


@dataclass(slots=True, frozen=True)
class ServiceState:
    name: str
    present: bool
    active: bool = False
    enabled: bool = False
    raw_active: str = ""
    raw_enabled: str = ""


@dataclass(slots=True, frozen=True)
class PackageState:
    name: str
    installed: bool
    version: str | None = None
    manager: str = "none"


@dataclass(slots=True, frozen=True)
class CommandProbe:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0
