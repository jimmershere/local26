from __future__ import annotations

import configparser
import grp
import os
import pwd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG_PATH, resolve_config_path


@dataclass(slots=True)
class Actor:
    user: str
    uid: int
    groups: set[str] = field(default_factory=set)


@dataclass(slots=True)
class AccessPolicy:
    source: Path | None = None
    configured: bool = False
    allowed_users: set[str] = field(default_factory=set)
    denied_users: set[str] = field(default_factory=set)
    allowed_groups: set[str] = field(default_factory=set)
    deny_root: bool = False
    allow_remote_cmd: bool = True
    parse_errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PolicyFinding:
    level: str
    control: str
    detail: str

    def render(self) -> str:
        return f"[{self.level}] {self.control}: {self.detail}"


def _csv_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _parse_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool, errors: list[str]) -> bool:
    if parser.has_option(section, option):
        try:
            return parser.getboolean(section, option)
        except ValueError:
            errors.append(f"[{section}] {option} must be true or false")
    return fallback


def _name_for_uid(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _name_for_gid(gid: int) -> str | None:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return None


def current_actor() -> Actor:
    uid = os.geteuid()
    user = _name_for_uid(uid)
    groups: set[str] = set()
    for gid in {os.getegid(), *os.getgroups()}:
        group_name = _name_for_gid(gid)
        if group_name:
            groups.add(group_name)
    return Actor(user=user, uid=uid, groups=groups)


def load_access_policy(path: str | Path = DEFAULT_CONFIG_PATH) -> AccessPolicy:
    try:
        config_path = resolve_config_path(path)
    except FileNotFoundError:
        return AccessPolicy()

    if config_path.suffix in {".yaml", ".yml"}:
        return AccessPolicy(source=config_path)

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(config_path, encoding="utf-8")
    policy = AccessPolicy(source=config_path, configured=parser.has_section("access"))
    if not parser.has_section("access"):
        return policy
    policy.allowed_users = _csv_set(parser.get("access", "allowed_users", fallback=""))
    policy.denied_users = _csv_set(parser.get("access", "denied_users", fallback=""))
    policy.allowed_groups = _csv_set(parser.get("access", "allowed_groups", fallback=""))
    policy.deny_root = _parse_bool(parser, "access", "deny_root", policy.deny_root, policy.parse_errors)
    policy.allow_remote_cmd = _parse_bool(parser, "access", "allow_remote_cmd", policy.allow_remote_cmd, policy.parse_errors)
    return policy


def evaluate_policy_config(policy: AccessPolicy) -> list[PolicyFinding]:
    return [
        PolicyFinding("FAIL", "CM-6 configuration settings", error)
        for error in policy.parse_errors
    ]


def evaluate_actor(policy: AccessPolicy, actor: Actor | None = None) -> list[PolicyFinding]:
    actor = actor or current_actor()
    findings: list[PolicyFinding] = []
    if policy.deny_root and actor.uid == 0:
        findings.append(PolicyFinding("FAIL", "AC-6 least privilege", "root execution is denied by policy"))
    if actor.user in policy.denied_users:
        findings.append(PolicyFinding("FAIL", "AC-2 account management", f"user {actor.user!r} is denied by policy"))
    if policy.allowed_users and actor.user not in policy.allowed_users:
        findings.append(PolicyFinding("FAIL", "AC-3 access enforcement", f"user {actor.user!r} is not in allowed_users"))
    if policy.allowed_groups and actor.groups.isdisjoint(policy.allowed_groups):
        allowed = ", ".join(sorted(policy.allowed_groups))
        findings.append(PolicyFinding("FAIL", "AC-3 access enforcement", f"actor is not a member of allowed_groups: {allowed}"))
    return findings


def _iter_steps(plan_data: dict[str, Any]):
    for scope in plan_data.get("scopes", []):
        for step in scope.get("steps", []):
            yield step


def evaluate_plan(policy: AccessPolicy, plan_data: dict[str, Any]) -> list[PolicyFinding]:
    findings: list[PolicyFinding] = []
    remote_steps = [step.get("id", "(unknown)") for step in _iter_steps(plan_data) if step.get("type") == "remote_cmd"]
    if remote_steps and not policy.allow_remote_cmd:
        findings.append(
            PolicyFinding(
                "FAIL",
                "CM-5 privileged functions",
                f"remote_cmd steps require access.allow_remote_cmd = true: {', '.join(remote_steps)}",
            )
        )
    return findings


def compliance_findings(policy: AccessPolicy | None = None) -> list[PolicyFinding]:
    policy = policy or load_access_policy()
    findings: list[PolicyFinding] = []
    findings.extend(evaluate_policy_config(policy))
    if policy.configured:
        findings.append(PolicyFinding("PASS", "AC-3 access enforcement", f"access policy loaded from {policy.source}"))
    else:
        findings.append(PolicyFinding("WARN", "AC-3 access enforcement", "no [access] policy configured"))
    if policy.allowed_users or policy.allowed_groups:
        findings.append(PolicyFinding("PASS", "AC-2 account management", "allowed users/groups are restricted"))
    else:
        findings.append(PolicyFinding("WARN", "AC-2 account management", "allowed users/groups are not restricted"))
    if policy.deny_root:
        findings.append(PolicyFinding("PASS", "AC-6 least privilege", "root execution is denied"))
    else:
        findings.append(PolicyFinding("WARN", "AC-6 least privilege", "root execution is not denied"))
    if policy.allow_remote_cmd:
        findings.append(PolicyFinding("WARN", "CM-5 privileged functions", "remote command steps are allowed"))
    else:
        findings.append(PolicyFinding("PASS", "CM-5 privileged functions", "remote command steps are denied by default"))
    findings.append(PolicyFinding("PASS", "AC-6 least privilege", "runtime directories and artifacts are owner-only by design"))
    findings.extend(evaluate_actor(policy))
    return findings


def enforce_deploy_policy(plan_data: dict[str, Any]) -> list[PolicyFinding]:
    policy = load_access_policy()
    return [*evaluate_policy_config(policy), *evaluate_actor(policy), *evaluate_plan(policy, plan_data)]
