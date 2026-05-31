from __future__ import annotations

import json
from argparse import Namespace
from typing import Any

from local26.config import DEFAULT_CONFIG_PATH

from .artifacts import new_run_dir, write_reports
from .config import DatabaseConfigError, load_database_targets
from .models import DatabaseTarget, DbReport
from .registry import adapter_for


def _select_targets(targets: list[DatabaseTarget], *, target_name: str | None, engine: str | None) -> list[DatabaseTarget]:
    selected = [target for target in targets if target.enabled]
    if target_name:
        selected = [target for target in selected if target.name == target_name]
    if engine:
        selected = [target for target in selected if target.engine == engine]
    return selected


def _print_text(reports: list[DbReport], run_dir: object) -> None:
    print("Local-26 database operations")
    print("============================")
    print(f"Artifacts: {run_dir}\n")
    for report in reports:
        print(f"{report.target.name} ({report.target.engine})")
        print(f"  action: {report.action}")
        print(f"  locator: {report.target.locator()}")
        if report.tools:
            available = ", ".join(tool.name for tool in report.tools if tool.available) or "none"
            missing = ", ".join(tool.name for tool in report.tools if not tool.available) or "none"
            print(f"  tools available: {available}")
            print(f"  tools missing: {missing}")
        if report.command_plans:
            print("  command plans:")
            for plan in report.command_plans:
                suffix = " (--execute required)" if plan.execute_required else ""
                print(f"    - {plan.name}: {' '.join(plan.argv)}{suffix}")
        print("  findings:")
        for finding in report.findings:
            print(f"    [{finding.level}] {finding.code}: {finding.detail}")
        print()


def _json_payload(run_dir: object, reports: list[DbReport]) -> dict[str, Any]:
    return {"artifacts": str(run_dir), "reports": [report.as_dict() for report in reports]}


def run_database_command(args: Namespace) -> int:
    config_path = args.config or DEFAULT_CONFIG_PATH
    try:
        targets = load_database_targets(config_path)
    except FileNotFoundError as exc:
        print(f"database config missing: {exc}")
        return 1
    except DatabaseConfigError as exc:
        print(f"database config invalid: {exc}")
        return 1
    selected = _select_targets(targets, target_name=args.target, engine=args.engine)
    if not selected:
        print("No enabled database targets matched the request.")
        return 1
    run_dir = new_run_dir(args.output_dir, args.db_command)
    reports = [
        adapter_for(target).run(args.db_command, execute=args.execute, quick=args.quick, backup_path=getattr(args, "backup_path", None))
        for target in selected
    ]
    write_reports(run_dir, reports)
    if args.format == "json":
        print(json.dumps(_json_payload(run_dir, reports), indent=2, sort_keys=True))
    else:
        _print_text(reports, run_dir)
    return 1 if any(report.failed() for report in reports) else 0
