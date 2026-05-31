from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    dry_run: bool = False


@dataclass(slots=True)
class ScopeConfig:
    name: str
    enabled: bool
    source_dir: Path
    target_dir: Path
    servers: list[str]
    discovery: str
    rsync_opts: str | None = None
    backup: bool | None = None
    backup_suffix: str | None = None


@dataclass(slots=True)
class PlanStep:
    id: str
    scope: str
    type: str
    command: list[str] = field(default_factory=list)
    host: str | None = None
    timeout_seconds: int | None = None


@dataclass(slots=True)
class Plan:
    plan_id: str
    mode: str
    scopes: list[dict]
    created_at: str
    schema: str = "local81.plan.v0.1"


@dataclass(slots=True)
class RunRecord:
    run_id: str
    plan_id: str | None
    started_at: str
    finished_at: str | None = None
    result: str | None = None
    exit_code: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
