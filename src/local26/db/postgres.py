from __future__ import annotations

from .adapters import DatabaseAdapter, available_tool_names
from .models import CommandPlan, DbReport, Finding


class Postgres17Adapter(DatabaseAdapter):
    engine = "postgres17"
    tool_purposes = {
        "psql": "PostgreSQL SQL runner",
        "pg_dump": "logical database backup",
        "pg_dumpall": "cluster-wide logical backup",
        "pg_basebackup": "physical base backup",
        "pg_verifybackup": "physical backup verification",
        "barman": "PostgreSQL backup manager",
        "pgbackrest": "PostgreSQL backup manager",
        "postgres_exporter": "Prometheus PostgreSQL exporter",
        "pg_exporter": "advanced PostgreSQL exporter",
        "pgbadger": "PostgreSQL log analyzer",
    }

    def _conn_args(self) -> list[str]:
        settings = self.target.settings
        args: list[str] = []
        if settings.get("host"):
            args.extend(["--host", str(settings["host"])])
        if settings.get("port"):
            args.extend(["--port", str(settings["port"])])
        if settings.get("database"):
            args.extend(["--dbname", str(settings["database"])])
        if settings.get("username_env"):
            args.extend(["--username", f"${settings['username_env']}"])
        return args

    def command_plans(self, action: str, *, execute: bool = False) -> list[CommandPlan]:
        conn = self._conn_args()
        plans = [
            CommandPlan("psql-version", ["psql", *conn, "--tuples-only", "--command", "select version();"], "Check PostgreSQL version"),
            CommandPlan("psql-wal-archive", ["psql", *conn, "--command", "select name, setting from pg_settings where name in ('archive_mode','archive_command','wal_level');"], "Inspect WAL/archive settings"),
            CommandPlan("psql-extensions", ["psql", *conn, "--command", "select extname, extversion from pg_extension where extname in ('pgaudit','pg_stat_statements');"], "Inspect audit/statistics extensions"),
        ]
        if action in {"backup", "doctor", "report"}:
            plans.extend([
                CommandPlan("pg-dump-plan", ["pg_dump", *conn, "--format=custom", "--file", "<backup-file>"], "Plan logical backup", True),
                CommandPlan("pg-basebackup-plan", ["pg_basebackup", *conn, "--checkpoint=fast", "--write-recovery-conf", "--target", "<backup-dir>"], "Plan physical base backup", True),
                CommandPlan("barman-check", ["barman", "check", self.target.name], "Check Barman server backup readiness"),
                CommandPlan("pgbackrest-info", ["pgbackrest", "info", "--stanza", self.target.name], "Check pgBackRest stanza status"),
            ])
        if action in {"monitor", "doctor", "report"}:
            plans.append(CommandPlan("pgbadger-plan", ["pgbadger", "<postgresql-log-file>", "--outfile", "<report.html>"], "Plan PostgreSQL log report"))
        return plans

    def run(self, action: str, *, execute: bool = False, quick: bool = False, backup_path: str | None = None) -> DbReport:
        report = super().run(action, execute=execute, quick=quick, backup_path=backup_path)
        available = available_tool_names(report.tools)
        if "psql" not in available:
            report.findings.append(Finding("WARN", "postgres:psql-missing", "psql is not available", "Install PostgreSQL 17 client tools for live checks."))
        if "barman" not in available and "pgbackrest" not in available:
            report.findings.append(Finding("WARN", "postgres:backup-manager-missing", "Barman or pgBackRest was not found", "Install a managed backup tool or rely on native pg_dump/pg_basebackup plans."))
        if "pgbadger" not in available:
            report.findings.append(Finding("WARN", "postgres:pgbadger-missing", "pgBadger is not available for log reports"))
        report.findings.append(Finding("PASS", "postgres:safety", "PostgreSQL actions are redacted CLI/SQL plans and do not require live services in CI."))
        report.data["recommended_extensions"] = ["pgaudit", "pg_stat_statements"]
        report.data["monitoring_integrations"] = ["prometheus-community/postgres_exporter", "pgsty/pg_exporter", "CrunchyData/pgmonitor"]
        return report
