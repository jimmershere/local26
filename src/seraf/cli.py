from __future__ import annotations

import argparse

from .commands.deploy import run_deploy
from .commands.doctor import run_doctor
from .commands.init import run_init
from .commands.plan import run_plan
from .commands.status import run_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seraf")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--import", dest="import_path", default=None)
    init.add_argument("--force", action="store_true")
    init.add_argument("--project", default=None)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--plan", default=None)

    sub.add_parser("status")

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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        return run_init(import_path=args.import_path, force=args.force, project=args.project)
    if args.command == "doctor":
        return run_doctor(plan=args.plan)
    if args.command == "status":
        return run_status()
    if args.command == "plan":
        return run_plan(only_scope=args.scope, output_format=args.format, print_stdout=args.stdout, ci_mode=args.ci, summary=args.summary)
    if args.command == "deploy":
        return run_deploy(plan=args.plan, scope=args.scope, max_parallel=args.max_parallel, rollback_on_failure=args.rollback_on_failure)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
