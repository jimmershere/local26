from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
STATUS_TO_LEVEL = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "unknown": "WARN", "not_applicable": "WARN", "waived": "WARN"}


@dataclass(frozen=True, slots=True)
class ComplianceRule:
    rule_id: str
    title: str
    category: str
    severity: str
    controls: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    remediation: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "category": self.category,
            "severity": self.severity,
            "controls": list(self.controls),
            "evidence_sources": list(self.evidence_sources),
            "remediation": self.remediation,
            "description": self.description,
        }


@dataclass(slots=True)
class ComplianceFinding:
    rule_id: str
    title: str
    status: str
    severity: str
    category: str
    subject: str
    message: str
    controls: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    remediation: str = ""
    source: str = ""
    location: str | None = None
    confidence: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def level(self) -> str:
        return STATUS_TO_LEVEL.get(self.status, "WARN")

    def render(self) -> str:
        location = f" ({self.location})" if self.location else ""
        return f"[{self.level}] {self.rule_id} {self.title}{location}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "status": self.status,
            "level": self.level,
            "severity": self.severity,
            "category": self.category,
            "subject": self.subject,
            "message": self.message,
            "controls": self.controls,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "source": self.source,
            "location": self.location,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class InventoryItem:
    kind: str
    path: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "detail": self.detail, "metadata": self.metadata}


@dataclass(slots=True)
class HardenPlanItem:
    rule_id: str
    title: str
    severity: str
    subject: str
    recommendation: str
    safe_to_autofix: bool = False
    requires_review: bool = True
    location: str | None = None
    controls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "subject": self.subject,
            "recommendation": self.recommendation,
            "safe_to_autofix": self.safe_to_autofix,
            "requires_review": self.requires_review,
            "location": self.location,
            "controls": self.controls,
        }


@dataclass(slots=True)
class InventoryReport:
    root: Path
    items: list[InventoryItem]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "local81.compliance.inventory.v0.1",
            "generated_at": self.generated_at,
            "root": str(self.root),
            "summary": {"items": len(self.items)},
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(slots=True)
class ComplianceReport:
    root: Path
    profile: str
    findings: list[ComplianceFinding]
    inventory: list[InventoryItem]
    generated_at: str

    def summary(self) -> dict[str, int]:
        counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "waived": 0}
        for finding in self.findings:
            counts[finding.status] = counts.get(finding.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "local81.compliance.report.v0.1",
            "generated_at": self.generated_at,
            "profile": self.profile,
            "root": str(self.root),
            "summary": self.summary(),
            "findings": [finding.to_dict() for finding in self.findings],
            "inventory": [item.to_dict() for item in self.inventory],
        }


@dataclass(slots=True)
class HardenPlan:
    root: Path
    profile: str
    items: list[HardenPlanItem]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "local81.compliance.harden_plan.v0.1",
            "generated_at": self.generated_at,
            "profile": self.profile,
            "root": str(self.root),
            "summary": {"items": len(self.items), "mutating_actions": 0},
            "items": [item.to_dict() for item in self.items],
        }
