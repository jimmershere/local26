from __future__ import annotations
import configparser

from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

from local81.compliance import build_harden_plan, build_inventory, scan_compliance
from local81.compliance.artifacts import write_artifacts
from local81.compliance.models import SEVERITY_ORDER
from local81.compliance.renderers import render_harden_plan, render_inventory, render_report
from local81.config import DEFAULT_CONFIG_PATH, resolve_config_path

def _load_defaults() -> dict[str, Any]:
    try:
        config_path = resolve_config_path(DEFAULT_CONFIG_PATH)
    except FileNotFoundError:
        return {}
    try:
        if config_path.suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            compliance = data.get("compliance") if isinstance(data, dict) else {}
            return compliance if isinstance(compliance, dict) else {}
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(config_path, encoding="utf-8")
        return dict(parser.items("compliance")) if parser.has_section("compliance") else {}
    except (OSError, configparser.Error, yaml.YAMLError):
        return {}


def _bool_default(value: object, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _profile(args: Namespace, defaults: dict[str, Any]) -> str:
    return args.compliance_profile or str(defaults.get("profile") or "nist-cms-local81")


def _scope(args: Namespace, defaults: dict[str, Any]) -> str:
    return args.scope or str(defaults.get("scope") or "all")


def _root(args: Namespace, defaults: dict[str, Any]) -> str:
    return args.path or args.root or str(defaults.get("root") or ".")


def _fail_on(args: Namespace, defaults: dict[str, Any]) -> str:
    return args.fail_on or str(defaults.get("fail_on") or "high")


def _include_passed(args: Namespace, defaults: dict[str, Any]) -> bool:
    if args.include_passed is not None:
        return bool(args.include_passed)
    return _bool_default(defaults.get("include_passed"), True)


def _output_dir(args: Namespace, defaults: dict[str, Any]) -> str | Path | None:
    return args.output_dir or defaults.get("report_dir")


def _run_id(prefix: str, generated_at: str) -> str:
    return f"{generated_at.replace(':', '').replace('-', '')}-{prefix}"


def _should_fail(report, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    threshold = SEVERITY_ORDER[fail_on]
    for finding in report.findings:
        if finding.status == "fail" and SEVERITY_ORDER.get(finding.severity, 0) >= threshold:
            return True
    return False


def run_compliance(args: Namespace) -> int:
    defaults = _load_defaults()
    root = _root(args, defaults)
    output_dir = _output_dir(args, defaults)
    if args.compliance_command == "inventory":
        report = build_inventory(root)
        text = render_inventory(report, args.format)
        print(text)
        write_artifacts(output_dir, run_id=_run_id("inventory", report.generated_at), text=text)
        return 0
    if args.compliance_command == "harden-plan":
        report = scan_compliance(root, scope=_scope(args, defaults), profile=_profile(args, defaults), include_passed=_include_passed(args, defaults))
        plan = build_harden_plan(report)
        text = render_harden_plan(plan, args.format)
        print(text)
        write_artifacts(output_dir, run_id=_run_id("harden-plan", plan.generated_at), text=text)
        return 0
    report = scan_compliance(root, scope=_scope(args, defaults), profile=_profile(args, defaults), include_passed=_include_passed(args, defaults))
    text = render_report(report, args.format)
    json_text = render_report(report, "json")
    print(text)
    write_artifacts(output_dir, run_id=_run_id("report", report.generated_at), text=text, json_text=json_text)
    return 1 if _should_fail(report, _fail_on(args, defaults)) else 0


def run_compliance_report() -> int:
    args = Namespace(
        compliance_command="report",
        compliance_profile=None,
        root=".",
        path=None,
        scope="access",
        format="text",
        include_passed=True,
        fail_on="low",
        output_dir=None,
    )
    return run_compliance(args)
