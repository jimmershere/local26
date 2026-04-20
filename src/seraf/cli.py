from __future__ import annotations

import argparse

from .commands.deploy import run_deploy
from .commands.diff import run_diff
from .commands.doctor import run_doctor
from .commands.guided import run_guided
from .commands.history import run_history
from .commands.hooks import run_hooks
from .commands.init import run_init
from .commands.logs import run_logs
from .commands.plan import run_plan
from .commands.profiles import run_profile_create, run_profiles
from .commands.status import run_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seraf")
    parser.add_argument("--profile", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--import", dest="import_path", default=None)
    init.add_argument("--force", action="store_true")
    init.add_argument("--project", default=None)
    init.add_argument("--guided", action="store_true")

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--plan", default=None)

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
    deploy.add_argument("--plan", required=True)
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

    history = sub.add_parser("history")
    history.add_argument("--limit", type=int, default=20)

    logs = sub.add_parser("logs")
    logs.add_argument("run_id")

    diff = sub.add_parser("diff")
    diff.add_argument("plan_a")
    diff.add_argument("plan_b")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        if args.guided:
            return run_guided(force=args.force)
        return run_init(import_path=args.import_path, force=args.force, project=args.project)
    if args.command == "doctor":
        return run_doctor(plan=args.plan, profile=args.profile)
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
        return run_deploy(plan=args.plan, scope=args.scope, max_parallel=args.max_parallel,
                          rollback_on_failure=args.rollback_on_failure, step_timeout=args.step_timeout,
                          fail_fast=args.fail_fast, dry_run=args.dry_run, check=args.check,
                          hosts_file=args.hosts_file, parallel=args.parallel, profile=args.profile,
                          notify=args.notify, quiet=args.quiet)
    if args.command == "history":
        return run_history(limit=args.limit)
    if args.command == "logs":
        return run_logs(args.run_id)
    if args.command == "diff":
        return run_diff(args.plan_a, args.plan_b)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
