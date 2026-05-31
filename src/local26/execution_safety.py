from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ExecutionFinding:
    level: str
    control: str
    scope: str
    step_id: str
    detail: str

    def render(self) -> str:
        return f"[{self.level}] {self.control}: scope={self.scope} step={self.step_id}: {self.detail}"


def _shell_operator_hits(command: str) -> list[str]:
    hits: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            index += 1
            continue
        if quote == "'":
            index += 1
            continue
        for token, label in (
            ("&&", "control operator &&"),
            ("||", "control operator ||"),
            ("$(", "command substitution $("),
        ):
            if command.startswith(token, index):
                hits.append(label)
                index += len(token)
                break
        else:
            if quote is None:
                if char == "|":
                    hits.append("pipeline |")
                elif char == ";":
                    hits.append("command separator ;")
                elif char in {">", "<"}:
                    hits.append(f"redirection {char}")
            elif char == "`":
                hits.append("command substitution `")
            index += 1
            continue
        continue
    return sorted(set(hits))


def _contains_token(command: str, token: str) -> bool:
    try:
        return token in shlex.split(command)
    except ValueError:
        return f" {token} " in f" {command} "


def _step_command_findings(scope_name: str, step: dict[str, Any]) -> list[ExecutionFinding]:
    step_id = str(step.get("id", "?"))
    command = str(step.get("cmd", ""))
    findings: list[ExecutionFinding] = []
    if step.get("type") == "remote_cmd":
        findings.append(ExecutionFinding(
            "WARN",
            "CM-5 privileged functions",
            scope_name,
            step_id,
            "remote_cmd executes through ssh on the target host",
        ))
    operator_hits = _shell_operator_hits(command)
    if operator_hits:
        findings.append(ExecutionFinding(
            "WARN",
            "CM-7 least functionality",
            scope_name,
            step_id,
            "shell features require review: " + ", ".join(operator_hits),
        ))
    if _contains_token(command, "sudo") or "sudo " in command:
        findings.append(ExecutionFinding(
            "WARN",
            "AC-6 least privilege",
            scope_name,
            step_id,
            "command references sudo",
        ))
    if step.get("rollback") and isinstance(step.get("rollback"), dict) and step["rollback"].get("cmd"):
        findings.append(ExecutionFinding(
            "WARN",
            "CP-10 system recovery",
            scope_name,
            step_id,
            "rollback command will execute after successful step if rollback-on-failure is requested",
        ))
    if step.get("on_failure") and isinstance(step.get("on_failure"), dict) and step["on_failure"].get("cmd"):
        findings.append(ExecutionFinding(
            "WARN",
            "SI-2 flaw remediation",
            scope_name,
            step_id,
            "step-level on_failure command may execute after failure",
        ))
    return findings


def summarize_execution_risks(plan_data: dict[str, Any]) -> list[ExecutionFinding]:
    findings: list[ExecutionFinding] = []
    for scope_item in plan_data.get("scopes", []):
        scope_name = str(scope_item.get("scope", "(unnamed)"))
        for step in scope_item.get("steps", []):
            findings.extend(_step_command_findings(scope_name, step))
    global_on_failure = plan_data.get("on_failure")
    if isinstance(global_on_failure, dict) and global_on_failure.get("cmd"):
        findings.append(ExecutionFinding(
            "WARN",
            "SI-2 flaw remediation",
            "(global)",
            "(on_failure)",
            "plan-level on_failure command may execute after failure",
        ))
    return findings
