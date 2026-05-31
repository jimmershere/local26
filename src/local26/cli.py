from __future__ import annotations

import argparse
import sys

from .commands.compliance import run_compliance_report
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
  local26 init [--import PATH] [--force] [--project NAME] [--guided]
  local26 doctor [--plan PATH]
  local26 compliance report
  local26 status
  local26 hooks
  local26 profiles
  local26 profile create NAME
  local26 plan [--scope NAME] [--format json] [--stdout] [--ci] [--summary]
  local26 deploy (--plan PATH | --latest) [--dry-run] [--scope NAME] [--max-parallel N]
  local26 pull [--scope NAME] [--hosts CSV] [--rsync-opts OPTS] [--dry-run]
  local26 history [--limit N]
  local26 logs RUN_ID
  local26 diag [--project NAME] [--hosts CSV] [--diag-type NAME] [--pid PID]
  local26 pull-logs [--settings PATH] [--hosts CSV] [--dest DIR]
  local26 diff PLAN_A PLAN_B
  local26 help"""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local26")
    parser.add_argument("--profile", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--import", dest="import_path", default=None)
    init.add_argument("--force", action="store_true")
    init.add_argument("--project", default=None)
    init.add_argument("--guided", action="store_true")

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--plan", default=None)
    compliance = sub.add_parser("compliance")
    compliance_sub = compliance.add_subparsers(dest="compliance_command", required=True)
    compliance_sub.add_parser("report")

    sub.add_parser("status")
    sub.add_parser("hooks")
    sub.add_parser("profiles")

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_create = profile_sub.add_parser("create")
    profile_create.add_argument("name")

    plan = sub.add_parser("plan")
    plan.add_argument("--scope", default=None)
    plan.add_argument("--format", default="json")
    plan.add_argument("--stdout", action="store_true")
    plan.add_argument("--ci", action="store_true")
    plan.add_argument("--summary", action="store_true")

    deploy = sub.add_parser("deploy")
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
    deploy.add_argument("--hosts-file", default=None)
    deploy.add_argument("--parallel", action="store_true")
    deploy.add_argument("--notify", action="store_true")
    deploy.add_argument("--quiet", action="store_true")

    pull = sub.add_parser("pull")
    pull.add_argument("--scope", default=None)
    pull.add_argument("--hosts", default=None)
    pull.add_argument("--rsync-opts", default=None)
    pull.add_argument("--dry-run", action="store_true")

    history = sub.add_parser("history")
    history.add_argument("--limit", type=int, default=20)

    pull_logs = sub.add_parser("pull-logs")
    pull_logs.add_argument("--settings", default="./settings.cfg")
    pull_logs.add_argument("--hosts", default=None)
    pull_logs.add_argument("--dest", default=None)
    pull_logs.add_argument("--jboss-path", default=None)
    pull_logs.add_argument("--apache-path", default=None)
    pull_logs.add_argument("--engin-path", default=None)
    pull_logs.add_argument("--smartxfr-path", default=None)

    diag = sub.add_parser("diag")
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

    logs = sub.add_parser("logs")
    logs.add_argument("run_id")

    diff = sub.add_parser("diff")
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
    if args.command == "compliance":
        if args.compliance_command == "report":
            return run_compliance_report()
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
                          hosts_file=args.hosts_file, parallel=args.parallel, profile=args.profile,
                          notify=args.notify, quiet=args.quiet)
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
        return run_logs(args.run_id)
    if args.command == "diff":
        return run_diff(args.plan_a, args.plan_b)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
