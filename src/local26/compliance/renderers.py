from __future__ import annotations

import json
from typing import Any

from .models import ComplianceReport, HardenPlan, InventoryReport


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def render_inventory(report: InventoryReport, output_format: str) -> str:
    if output_format == "json":
        return _json(report.to_dict())
    if output_format == "markdown":
        lines = ["# Local-26 compliance inventory", f"- Root: `{report.root}`", f"- Items: {len(report.items)}", ""]
        if report.items:
            lines.append("## Items")
            for item in report.items:
                lines.append(f"- `{item.kind}`: `{item.path}` ({item.detail})")
        else:
            lines.append("No evidence candidates were discovered in this scan.")
        return "\n".join(lines)
    lines = ["Local-26 compliance inventory", "=============================", f"Root: {report.root}", f"Items: {len(report.items)}", ""]
    for item in report.items:
        lines.append(f"- {item.kind}: {item.path} ({item.detail})")
    return "\n".join(lines)


def render_report(report: ComplianceReport, output_format: str) -> str:
    if output_format == "json":
        return _json(report.to_dict())
    summary = report.summary()
    warning_count = summary.get("warn", 0) + summary.get("unknown", 0)
    if output_format == "markdown":
        lines = [
            "# Local-26 compliance report",
            f"- Profile: `{report.profile}`",
            f"- Root: `{report.root}`",
            f"- Findings: {len(report.findings)} ({summary.get('pass', 0)} pass, {warning_count} warnings, {summary.get('fail', 0)} failures)",
            "",
        ]
        if report.findings:
            lines.append("## Findings")
            for finding in report.findings:
                location = f" `{finding.location}`" if finding.location else ""
                lines.append(f"- **{finding.level}** `{finding.rule_id}` {finding.title}{location}: {finding.message}")
        else:
            lines.append("No findings were emitted for this scan.")
        if summary.get("fail", 0):
            lines.append("\nReview failed findings before treating this host or project as hardened.")
        elif warning_count:
            lines.append("\nReview warning or unknown findings before relying on this scan.")
        else:
            lines.append("\nNo failed or warning findings were found in this scan.")
        return "\n".join(lines)
    lines = [
        "Local-26 compliance report",
        "==========================",
        f"Profile: {report.profile}",
        f"Root: {report.root}",
        (
            f"Checked {len(report.findings)} findings: {summary.get('pass', 0)} pass, "
            f"{warning_count} warnings, {summary.get('fail', 0)} failures."
        ),
        "",
    ]
    for finding in report.findings:
        lines.append(f"  {finding.render()}")
    if summary.get("fail", 0):
        lines.append("\nCompliance report found failed hardening findings to review.")
    elif warning_count:
        lines.append("\nCompliance report found warning or unknown findings to review.")
    else:
        lines.append("\nNo failed or warning findings were found in this scan.")
    return "\n".join(lines)


def render_harden_plan(plan: HardenPlan, output_format: str) -> str:
    if output_format == "json":
        return _json(plan.to_dict())
    if output_format == "markdown":
        lines = ["# Local-26 hardening plan", f"Root: `{plan.root}`", "", "All actions are advisory and non-mutating.", ""]
        if plan.items:
            for item in plan.items:
                lines.extend([f"## {item.rule_id} {item.title}", f"- Severity: {item.severity}", f"- Subject: {item.subject}", f"- Recommendation: {item.recommendation}", ""])
        else:
            lines.append("No remediation items were generated from this scan.")
        return "\n".join(lines).rstrip()
    lines = ["Local-26 hardening plan", "=======================", f"Root: {plan.root}", "Actions are advisory and non-mutating.", ""]
    if plan.items:
        for item in plan.items:
            location = f" ({item.location})" if item.location else ""
            lines.append(f"- [{item.severity}] {item.rule_id} {item.title}{location}: {item.recommendation}")
    else:
        lines.append("No remediation items were generated from this scan.")
    return "\n".join(lines)
