from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Finding:
    level: str
    code: str
    detail: str
    recommendation: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = {"level": self.level, "code": self.code, "detail": self.detail}
        if self.recommendation:
            data["recommendation"] = self.recommendation
        return data


@dataclass(slots=True)
class ToolStatus:
    name: str
    available: bool
    path: str | None = None
    purpose: str = ""

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "available": self.available}
        if self.path:
            data["path"] = self.path
        if self.purpose:
            data["purpose"] = self.purpose
        return data


@dataclass(slots=True)
class CommandPlan:
    name: str
    argv: list[str]
    purpose: str
    execute_required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": self.argv,
            "purpose": self.purpose,
            "execute_required": self.execute_required,
        }


@dataclass(slots=True)
class DatabaseTarget:
    name: str
    engine: str
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def locator(self) -> str:
        for key in ("path", "dsn_env", "connect_env", "service_name", "service", "database", "host"):
            value = self.settings.get(key)
            if value:
                return str(value)
        return "unconfigured"

    def safe_settings(self) -> dict[str, Any]:
        from .redaction import redact_mapping

        return redact_mapping(self.settings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine": self.engine,
            "enabled": self.enabled,
            "tags": self.tags,
            "locator": self.locator(),
            "settings": self.safe_settings(),
        }


@dataclass(slots=True)
class DbReport:
    action: str
    target: DatabaseTarget
    findings: list[Finding] = field(default_factory=list)
    tools: list[ToolStatus] = field(default_factory=list)
    command_plans: list[CommandPlan] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target.as_dict(),
            "findings": [finding.as_dict() for finding in self.findings],
            "tools": [tool.as_dict() for tool in self.tools],
            "command_plans": [plan.as_dict() for plan in self.command_plans],
            "data": self.data,
        }

    def failed(self) -> bool:
        return any(finding.level == "FAIL" for finding in self.findings)
