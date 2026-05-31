from __future__ import annotations

from .adapters import DatabaseAdapter, available_tool_names
from .models import CommandPlan, DbReport, Finding


class Oracle19cAdapter(DatabaseAdapter):
    engine = "oracle19c"
    tool_purposes = {
        "sqlplus": "SQL*Plus query runner",
        "sql": "SQLcl query runner",
        "rman": "RMAN backup and recovery",
        "expdp": "Data Pump export",
        "impdp": "Data Pump import",
        "adrci": "Automatic Diagnostic Repository CLI",
        "lsnrctl": "listener status",
        "srvctl": "RAC/Grid service status",
        "crsctl": "Clusterware status",
        "ahf": "Autonomous Health Framework",
        "orachk": "Oracle health/compliance checks",
        "exachk": "Exadata health/compliance checks",
        "tfactl": "Trace File Analyzer",
    }

    def command_plans(self, action: str, *, execute: bool = False) -> list[CommandPlan]:
        service = str(self.target.settings.get("service_name") or self.target.settings.get("service") or self.target.name)
        plans = [
            CommandPlan("listener-status", ["lsnrctl", "status"], "Check Oracle listener status"),
            CommandPlan("adrci-alerts", ["adrci", "show", "alert", "-tail", "100"], "Inspect recent ADR alert entries"),
            CommandPlan("sqlplus-instance", ["sqlplus", "-L", "/nolog", "@local81_oracle_health.sql"], "Run read-only Oracle health SQL"),
        ]
        if action in {"backup", "doctor", "report"}:
            plans.append(CommandPlan("rman-validate", ["rman", "target", "/", "cmdfile=local81_rman_validate.rcv"], "Validate RMAN backup/readiness", True))
            plans.append(CommandPlan("datapump-export-plan", ["expdp", f"service_name={service}", "parfile=local81_export.par"], "Plan Data Pump export", True))
        if action in {"audit", "doctor", "report"}:
            plans.append(CommandPlan("orachk-security", ["orachk", "-profile", "security", "-nodaemon"], "Run ORAchk security profile", True))
            plans.append(CommandPlan("ahf-insights", ["ahf", "analysis", "create", "--type", "insights", "--last", "2h"], "Generate AHF Insights diagnostics", True))
        if action in {"monitor", "diag", "doctor"}:
            plans.append(CommandPlan("tfa-status", ["tfactl", "print", "status"], "Check Trace File Analyzer status"))
            plans.append(CommandPlan("rac-status", ["srvctl", "status", "database", "-db", service], "Check RAC database status when Grid tools exist"))
        return plans

    def run(self, action: str, *, execute: bool = False, quick: bool = False, backup_path: str | None = None) -> DbReport:
        report = super().run(action, execute=execute, quick=quick, backup_path=backup_path)
        available = available_tool_names(report.tools)
        if {"sqlplus", "sql"}.isdisjoint(available):
            report.findings.append(Finding("WARN", "oracle:sql-runner-missing", "SQL*Plus or SQLcl is not available", "Install Oracle Instant Client SQL*Plus or SQLcl for live checks."))
        if "rman" not in available:
            report.findings.append(Finding("WARN", "oracle:rman-missing", "RMAN is not available", "Install Oracle database client/server tools on the managed host for backup validation."))
        if "orachk" not in available and "ahf" not in available:
            report.findings.append(Finding("WARN", "oracle:ahf-missing", "Oracle AHF/ORAchk was not found", "Install Oracle AHF where licensed/supportable for compliance checks."))
        report.findings.append(Finding("PASS", "oracle:safety", "Oracle actions are emitted as redacted command plans; mutating work requires --execute."))
        return report
