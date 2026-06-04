from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import DbReport


def new_run_dir(base: str | Path | None, action: str) -> Path:
    root = Path(base) if base else Path(".local81/db")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{stamp}-{action}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_reports(run_dir: Path, reports: list[DbReport]) -> None:
    summary = {
        "schema": "local81.db.report.v0.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "reports": [report.as_dict() for report in reports],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["Local-81 database report", "========================", ""]
    for report in reports:
        lines.append(f"{report.target.name} ({report.target.engine}) — {report.action}")
        for finding in report.findings:
            lines.append(f"  [{finding.level}] {finding.code}: {finding.detail}")
            if finding.recommendation:
                lines.append(f"    recommendation: {finding.recommendation}")
        lines.append("")
    (run_dir / "report.txt").write_text("\n".join(lines), encoding="utf-8")
