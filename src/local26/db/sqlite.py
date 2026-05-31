from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .adapters import DatabaseAdapter
from .models import CommandPlan, DbReport, Finding


class SQLiteAdapter(DatabaseAdapter):
    engine = "sqlite"
    tool_purposes = {
        "sqlite3": "SQLite shell",
        "sqldiff": "SQLite database diff",
        "sqlite3_analyzer": "SQLite storage analyzer",
        "sqlite3_rsync": "SQLite live remote copy",
        "litestream": "SQLite streaming backup/replication",
        "sqlite-utils": "SQLite utility CLI",
    }

    def _path(self) -> Path | None:
        value = self.target.settings.get("path")
        return Path(str(value)).expanduser() if value else None

    def command_plans(self, action: str, *, execute: bool = False) -> list[CommandPlan]:
        path = str(self.target.settings.get("path", "<database.sqlite>"))
        plans = [
            CommandPlan("sqlite-quick-check", ["sqlite3", path, "PRAGMA quick_check;"], "Run quick corruption check"),
            CommandPlan("sqlite-foreign-key-check", ["sqlite3", path, "PRAGMA foreign_key_check;"], "Check foreign key violations"),
            CommandPlan("sqlite-analyzer", ["sqlite3_analyzer", path], "Generate storage utilization report"),
        ]
        if action in {"backup", "doctor", "report"}:
            plans.append(CommandPlan("sqlite-vacuum-into", ["sqlite3", path, "VACUUM INTO '<backup-file>';"], "Create compact consistent backup", True))
            plans.append(CommandPlan("sqlite-rsync", ["sqlite3_rsync", path, "<replica>"], "Create live local/remote consistent replica", True))
        return plans

    def _pragma_one(self, db: sqlite3.Connection, pragma: str) -> object:
        row = db.execute(f"PRAGMA {pragma}").fetchone()
        return row[0] if row else None

    def _inspect(self, report: DbReport, *, quick: bool) -> None:
        path = self._path()
        if path is None:
            report.findings.append(Finding("FAIL", "sqlite:path-missing", "SQLite target requires a path setting"))
            return
        report.data["path"] = str(path)
        if not path.exists():
            report.findings.append(Finding("FAIL", "sqlite:file-missing", f"{path} does not exist"))
            return
        if not path.is_file():
            report.findings.append(Finding("FAIL", "sqlite:not-file", f"{path} is not a regular file"))
            return
        report.data["size_bytes"] = path.stat().st_size
        report.data["readable"] = os.access(path, os.R_OK)
        report.data["writable"] = os.access(path, os.W_OK)
        if not os.access(path, os.R_OK):
            report.findings.append(Finding("FAIL", "sqlite:not-readable", f"{path} is not readable"))
            return
        try:
            with path.open("rb") as handle:
                header = handle.read(16)
            if header != b"SQLite format 3\x00":
                report.findings.append(Finding("FAIL", "sqlite:bad-header", f"{path} does not have a SQLite format 3 header"))
                return
            uri = f"file:{path}?mode=ro"
            with sqlite3.connect(uri, uri=True) as db:
                db.row_factory = sqlite3.Row
                report.data["page_count"] = self._pragma_one(db, "page_count")
                report.data["page_size"] = self._pragma_one(db, "page_size")
                report.data["freelist_count"] = self._pragma_one(db, "freelist_count")
                report.data["journal_mode"] = self._pragma_one(db, "journal_mode")
                report.data["synchronous"] = self._pragma_one(db, "synchronous")
                report.data["foreign_keys"] = self._pragma_one(db, "foreign_keys")
                quick_result = self._pragma_one(db, "quick_check")
                report.data["quick_check"] = quick_result
                if quick_result == "ok":
                    report.findings.append(Finding("PASS", "sqlite:quick-check", "PRAGMA quick_check returned ok"))
                else:
                    report.findings.append(Finding("FAIL", "sqlite:quick-check", f"PRAGMA quick_check returned {quick_result!r}"))
                if not quick:
                    integrity_result = self._pragma_one(db, "integrity_check")
                    report.data["integrity_check"] = integrity_result
                    if integrity_result == "ok":
                        report.findings.append(Finding("PASS", "sqlite:integrity-check", "PRAGMA integrity_check returned ok"))
                    else:
                        report.findings.append(Finding("FAIL", "sqlite:integrity-check", f"PRAGMA integrity_check returned {integrity_result!r}"))
                fk_rows = [dict(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
                report.data["foreign_key_violations"] = fk_rows
                if fk_rows:
                    report.findings.append(Finding("WARN", "sqlite:foreign-key-violations", f"{len(fk_rows)} foreign key violations found"))
        except sqlite3.Error as exc:
            report.findings.append(Finding("FAIL", "sqlite:error", str(exc)))

    def _backup(self, report: DbReport, *, execute: bool, backup_path: str | None) -> None:
        source = self._path()
        destination = Path(backup_path).expanduser() if backup_path else None
        if not execute:
            report.findings.append(Finding("WARN", "sqlite:backup-dry-run", "backup is a dry run; pass --execute --backup-path PATH to create a copy"))
            return
        if source is None or destination is None:
            report.findings.append(Finding("FAIL", "sqlite:backup-path", "SQLite backup requires configured source path and --backup-path"))
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(destination) as dest:
                src.backup(dest)
            report.data["backup_path"] = str(destination)
            report.findings.append(Finding("PASS", "sqlite:backup", f"created SQLite backup at {destination}"))
        except sqlite3.Error as exc:
            report.findings.append(Finding("FAIL", "sqlite:backup", str(exc)))

    def run(self, action: str, *, execute: bool = False, quick: bool = False, backup_path: str | None = None) -> DbReport:
        report = super().run(action, execute=execute, quick=quick, backup_path=backup_path)
        self._inspect(report, quick=quick)
        if action == "backup":
            self._backup(report, execute=execute, backup_path=backup_path)
        report.findings.append(Finding("PASS", "sqlite:safety", "SQLite diagnostics open the database read-only; backups require --execute."))
        return report
