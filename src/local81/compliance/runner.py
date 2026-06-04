from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .models import ComplianceFinding, ComplianceReport, HardenPlan, HardenPlanItem, InventoryItem, InventoryReport
from .policy_adapter import scan_access_policy
from .scanner_javascript import scan_javascript
from .scanner_linux import scan_linux
from .scanner_web_java import scan_web_java


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_excluded(path: Path) -> bool:
    return any(part in {".git", "node_modules", "dist", "build", ".angular", ".next", ".turbo", "coverage", "__pycache__"} for part in path.parts)


def _inventory_items(root: Path) -> list[InventoryItem]:
    items: list[InventoryItem] = []
    candidates = {
        "linux-os": [root / "etc/os-release"],
        "linux-ssh": [root / "etc/ssh/sshd_config"],
        "linux-sysctl": [root / "etc/sysctl.conf", *sorted((root / "etc/sysctl.d").glob("*.conf"))],
        "web-apache": [*root.rglob("apache2.conf"), *root.rglob("httpd.conf")],
        "web-nginx": [*root.rglob("nginx.conf")],
        "tomcat": [*root.rglob("server.xml"), *root.rglob("tomcat-users.xml")],
        "node-package": [*root.rglob("package.json")],
        "node-npmrc": [*root.rglob(".npmrc")],
        "angular": [*root.rglob("angular.json"), *root.rglob("workspace.json")],
    }
    for kind, paths in candidates.items():
        for path in paths:
            if path.exists() and not _is_excluded(path):
                items.append(InventoryItem(kind=kind, path=str(path), detail="candidate discovered"))
    return items


def build_inventory(root: str | Path = ".") -> InventoryReport:
    root_path = Path(root).expanduser().resolve()
    return InventoryReport(root=root_path, items=_inventory_items(root_path), generated_at=_now())


def scan_compliance(root: str | Path = ".", *, scope: str = "all", profile: str = "nist-cms-local81", include_passed: bool = True) -> ComplianceReport:
    root_path = Path(root).expanduser().resolve()
    findings: list[ComplianceFinding] = []
    if scope in {"all", "access"}:
        findings.extend(scan_access_policy())
    if scope in {"all", "linux", "os"}:
        findings.extend(scan_linux(root_path))
    if scope in {"all", "web", "java"}:
        findings.extend(scan_web_java(root_path))
    if scope in {"all", "javascript", "node", "angular"}:
        findings.extend(scan_javascript(root_path))
    if not include_passed:
        findings = [finding for finding in findings if finding.status != "pass"]
    return ComplianceReport(root=root_path, profile=profile, findings=findings, inventory=_inventory_items(root_path), generated_at=_now())


def build_harden_plan(report: ComplianceReport) -> HardenPlan:
    items: list[HardenPlanItem] = []
    for finding in report.findings:
        if finding.status == "pass":
            continue
        items.append(
            HardenPlanItem(
                rule_id=finding.rule_id,
                title=finding.title,
                severity=finding.severity,
                subject=finding.subject,
                recommendation=finding.remediation,
                safe_to_autofix=False,
                requires_review=True,
                location=finding.location,
                controls=finding.controls,
            )
        )
    return HardenPlan(root=report.root, profile=report.profile, items=items, generated_at=_now())
