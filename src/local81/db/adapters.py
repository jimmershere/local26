from __future__ import annotations

import shutil

from .models import CommandPlan, DatabaseTarget, DbReport, Finding, ToolStatus


class DatabaseAdapter:
    engine = ""
    tool_purposes: dict[str, str] = {}

    def __init__(self, target: DatabaseTarget) -> None:
        self.target = target

    def discover_tools(self) -> list[ToolStatus]:
        tools: list[ToolStatus] = []
        for name, purpose in self.tool_purposes.items():
            path = shutil.which(name)
            tools.append(ToolStatus(name=name, available=path is not None, path=path, purpose=purpose))
        return tools

    def command_plans(self, action: str, *, execute: bool = False) -> list[CommandPlan]:
        return []

    def run(self, action: str, *, execute: bool = False, quick: bool = False, backup_path: str | None = None) -> DbReport:
        report = DbReport(action=action, target=self.target)
        report.tools = self.discover_tools()
        report.command_plans = self.command_plans(action, execute=execute)
        report.findings.append(Finding("PASS", f"{self.engine}:adapter", "adapter loaded"))
        if not self.target.enabled:
            report.findings.append(Finding("WARN", "target:disabled", "target is disabled in config"))
        return report


def available_tool_names(tools: list[ToolStatus]) -> set[str]:
    return {tool.name for tool in tools if tool.available}
