from __future__ import annotations

import argparse
import sys

from .commands.compliance import run_compliance
from .commands.db import run_db
from .commands.deploy import run_deploy
from .commands.diag import run_diag
from .commands.diff import run_diff
from .commands.doctor import run_doctor
from .commands.guided import run_guided
from .commands.history import run_history
from .commands.hooks import run_hooks
from .commands.init import run_init
from .commands.logs import run_logs
from .commands.plan import run_plan
from .commands.profiles import run_profile_create, run_profiles
from .commands.pull import run_pull
from .commands.pull_logs import run_pull_logs
from .commands.status import run_status

def print_command_reference() -> None:
    print(
        """Usage:
  local81 init [--import PATH] [--force] [--project NAME] [--guided]
  local81 doctor [--plan PATH]
  local81 db <doctor|inventory|tools|monitor|diag|backup|report|audit> [options]
  local81 compliance <report|inventory|harden-plan> [options]
  local81 status
  local81 hooks
  local81 profiles
  local81 profile create NAME
  local81 plan [--scope NAME] [--format json] [--stdout] [--ci] [--summary]
  local81 deploy (--plan PATH | --latest) [--dry-run] [--scope NAME] [--max-parallel N]
  local81 pull [--scope NAME] [--hosts CSV] [--rsync-opts OPTS] [--dry-run]
  local81 history [--limit N]
  local81 logs RUN_ID
  local81 diag [--project NAME] [--hosts CSV] [--diag-type NAME] [--pid PID]
  local81 pull-logs [--settings PATH] [--hosts CSV] [--dest DIR]
  local81 diff PLAN_A PLAN_B
  local81 help"""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="local81",
        description="Local-81 operator CLI for deploy planning, diagnostics, compliance checks, and database readiness.",
    )
    parser.add_argument("--profile", default=None, help="Apply a profile overlay from .local81/profiles/ when the command supports it.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    init = sub.add_parser("init", help="Create or import a .local81 project config.")
    init.add_argument("--import", dest="import_path", default=None)
    init.add_argument("--force", action="store_true")
    init.add_argument("--project", default=None)
    init.add_argument("--guided", action="store_true")

    doctor = sub.add_parser("doctor", help="Check environment and optional plan/config readiness.")
    doctor.add_argument("--plan", default=None)

    db = sub.add_parser("db", help="Run database readiness, diagnostic, backup-plan, and audit helpers.")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_help = {
        "doctor": "Validate database target config and tool readiness.",
        "inventory": "List configured database targets and discovered tools.",
        "tools": "Show database tool discovery status.",
        "monitor": "Show monitoring readiness plans.",
        "diag": "Run or plan database diagnostics.",
        "backup": "Plan backups, or execute supported SQLite backups with --execute.",
        "report": "Write database operation reports.",
        "audit": "Show database audit readiness checks.",
    }
    for db_command in ("doctor", "inventory", "tools", "monitor", "diag", "backup", "report", "audit"):
        db_parser = db_sub.add_parser(db_command, help=db_help[db_command])
        db_parser.add_argument("--config", default=None, help="Config file to read; defaults to .local81/config.ini with YAML fallback.")
        db_parser.add_argument("--target", default=None, help="Restrict to one database target name.")
        db_parser.add_argument("--engine", default=None, choices=("oracle19c", "postgres17", "sqlite"), help="Restrict to one database engine.")
        db_parser.add_argument("--output-dir", default=None, help="Artifact root; defaults to .local81/db.")
        db_parser.add_argument("--format", default="text", choices=("text", "json"), help="Terminal output format.")
        db_parser.add_argument("--execute", action="store_true", help="Allow supported state-changing actions.")
        db_parser.add_argument("--quick", action="store_true", help="Skip slower checks where supported.")
        if db_command == "backup":
            db_parser.add_argument("--backup-path", default=None, help="Destination path for executable SQLite backups.")
    compliance = sub.add_parser("compliance", help="Run read-only operational hardening checks and recommendations.")
    compliance_sub = compliance.add_subparsers(dest="compliance_command", required=True)
    compliance_help = {
        "report": "Print compliance findings mapped to selected NIST/CMS control themes.",
        "inventory": "List local evidence candidates without judging them.",
        "harden-plan": "Print manual remediation recommendations without changing files.",
    }
    for compliance_command in ("report", "inventory", "harden-plan"):
        compliance_parser = compliance_sub.add_parser(compliance_command, help=compliance_help[compliance_command])
        compliance_parser.add_argument("--root", default=None, help="Root path to inspect.")
        compliance_parser.add_argument("--path", default=None, help="Alias for --root.")
        compliance_parser.add_argument("--scope", default=None, choices=("all", "access", "linux", "os", "web", "java", "javascript", "node", "angular"), help="Restrict scanner scope.")
        compliance_parser.add_argument("--profile", dest="compliance_profile", default=None, help="Compliance profile label for the report.")
        compliance_parser.add_argument("--format", default="text", choices=("text", "json", "markdown"), help="Output format.")
        compliance_parser.add_argument("--include-passed", action=argparse.BooleanOptionalAction, default=None, help="Include passing findings; use --no-include-passed to show gaps only.")
        compliance_parser.add_argument("--fail-on", default=None, choices=("never", "low", "medium", "high", "critical"), help="Exit nonzero when a failed finding meets this severity.")
        compliance_parser.add_argument("--output-dir", default=None, help="Write artifacts under this directory.")

    sub.add_parser("status", help="Show current and latest deploy run state.")
    sub.add_parser("hooks", help="List supported hook paths and install status.")
    sub.add_parser("profiles", help="List profile overlays.")

    profile = sub.add_parser("profile", help="Manage profile overlays.")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_create = profile_sub.add_parser("create")
    profile_create.add_argument("name")

    plan = sub.add_parser("plan", help="Generate a deployment plan.")
    plan.add_argument("--scope", default=None)
    plan.add_argument("--format", default="json")
    plan.add_argument("--stdout", action="store_true")
    plan.add_argument("--ci", action="store_true")
    plan.add_argument("--summary", action="store_true")

    deploy = sub.add_parser("deploy", help="Execute a deployment plan.")
    deploy_target = deploy.add_mutually_exclusive_group(required=True)
    deploy_target.add_argument("--plan", default=None)
    deploy_target.add_argument("--latest", action="store_true")
    deploy.add_argument("--scope", default=None)
    deploy.add_argument("--max-parallel", type=int, default=1)
    deploy.add_argument("--rollback-on-failure", action="store_true")
    deploy.add_argument("--step-timeout", type=int, default=None)
    deploy.add_argument("--dry-run", action="store_true")
    deploy.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    deploy.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    deploy.set_defaults(fail_fast=False)
    deploy.add_argument("--check", action="store_true")
    deploy.add_argument("--allow-drift", action="store_true",
                        help="With --check: report target drift from the plan's desired state as a warning instead of failing.")
    deploy.add_argument("--hosts-file", default=None)
    deploy.add_argument("--parallel", action="store_true")
    deploy.add_argument("--notify", action="store_true")
    deploy.add_argument("--quiet", action="store_true")
    deploy.add_argument("--forks", type=int, default=None,
                        help="Fleet mode: max hosts executing concurrently within a batch (default 5).")
    deploy.add_argument("--serial", default=None,
                        help="Fleet mode: rolling batch size as N or N%% (default: one batch).")
    deploy.add_argument("--max-fail", dest="max_fail", default=None,
                        help="Fleet mode: abort new batches once failures reach N or N%% (default 0 = first failure).")
    deploy.add_argument("--limit", default=None,
                        help="Fleet mode: restrict to hosts matching a glob pattern.")

    pull = sub.add_parser("pull", help="Pull files back from configured remote hosts.")
    pull.add_argument("--scope", default=None)
    pull.add_argument("--hosts", default=None)
    pull.add_argument("--rsync-opts", default=None)
    pull.add_argument("--dry-run", action="store_true")

    history = sub.add_parser("history", help="Show recent deploy runs.")
    history.add_argument("--limit", type=int, default=20)

    pull_logs = sub.add_parser("pull-logs", help="Collect remote application logs.")
    pull_logs.add_argument("--settings", default="./settings.cfg")
    pull_logs.add_argument("--hosts", default=None)
    pull_logs.add_argument("--dest", default=None)
    pull_logs.add_argument("--jboss-path", default=None)
    pull_logs.add_argument("--apache-path", default=None)
    pull_logs.add_argument("--engin-path", default=None)
    pull_logs.add_argument("--smartxfr-path", default=None)

    diag = sub.add_parser("diag", help="Plan or run remote diagnostics.")
    diag.add_argument("--project", default=None)
    diag.add_argument("--hosts", default=None)
    diag.add_argument("--diag-type", default="strace")
    diag.add_argument("--pid", default=None)
    diag.add_argument("--duration", default="20s")
    diag.add_argument("--remote-cmd", default=None)
    diag.add_argument("--out-dir", default=None)
    diag.add_argument("--ssh-user", default=None)
    diag.add_argument("--include-disabled", action="store_true")
    diag.add_argument("--dry-run", action="store_true")

    logs = sub.add_parser("logs", help="Show logs for one run.")
    logs.add_argument("run_id")
    logs.add_argument("--host", default=None, help="Show the per-host log for a single fleet host.")

    diff = sub.add_parser("diff", help="Compare two deployment plan files.")
    diff.add_argument("plan_a")
    diff.add_argument("plan_b")

    return parser


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "help":
        print_command_reference()
        return 0
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        if args.guided:
            return run_guided(force=args.force)
        return run_init(import_path=args.import_path, force=args.force, project=args.project)
    if args.command == "doctor":
        return run_doctor(plan=args.plan, profile=args.profile)
    if args.command == "db":
        return run_db(args)
    if args.command == "compliance":
        return run_compliance(args)
    if args.command == "status":
        return run_status()
    if args.command == "hooks":
        return run_hooks()
    if args.command == "profiles":
        return run_profiles()
    if args.command == "profile":
        if args.profile_command == "create":
            return run_profile_create(args.name)
    if args.command == "plan":
        return run_plan(only_scope=args.scope, output_format=args.format, print_stdout=args.stdout, ci_mode=args.ci, summary=args.summary)
    if args.command == "deploy":
        return run_deploy(plan=args.plan, use_latest=args.latest, scope=args.scope, max_parallel=args.max_parallel,
                          rollback_on_failure=args.rollback_on_failure, step_timeout=args.step_timeout,
                          fail_fast=args.fail_fast, dry_run=args.dry_run, check=args.check,
                          allow_drift=args.allow_drift,
                          hosts_file=args.hosts_file, parallel=args.parallel, profile=args.profile,
                          notify=args.notify, quiet=args.quiet,
                          forks=args.forks, serial=args.serial, max_fail=args.max_fail, limit=args.limit)
    if args.command == "pull":
        return run_pull(scope=args.scope, hosts=args.hosts, rsync_opts=args.rsync_opts, dry_run=args.dry_run, profile=args.profile)
    if args.command == "history":
        return run_history(limit=args.limit)
    if args.command == "pull-logs":
        return run_pull_logs(settings=args.settings, hosts=args.hosts, dest=args.dest,
                             jboss_path=args.jboss_path, apache_path=args.apache_path,
                             engin_path=args.engin_path, smartxfr_path=args.smartxfr_path)
    if args.command == "diag":
        return run_diag(project=args.project, hosts=args.hosts, diag_type=args.diag_type,
                        pid=args.pid, duration=args.duration, remote_cmd=args.remote_cmd,
                        out_dir=args.out_dir, ssh_user=args.ssh_user,
                        include_disabled=args.include_disabled, dry_run=args.dry_run)
    if args.command == "logs":
        return run_logs(args.run_id, host=args.host)
    if args.command == "diff":
        return run_diff(args.plan_a, args.plan_b)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
