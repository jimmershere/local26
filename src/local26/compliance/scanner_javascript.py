from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .catalog import get_rule
from .models import ComplianceFinding


EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".angular", ".next", ".turbo", "coverage", "__pycache__"}
LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml")
LIFECYCLE_SCRIPTS = {"preinstall", "install", "postinstall", "prepare", "prepublish", "prepack"}
REMOTE_SHELL_RE = re.compile(r"(curl|wget).*(bash|sh)|npx\s+https?://|bash\s+-c\s+.*https?://", re.IGNORECASE)
SECRET_RE = re.compile(r"(api[_-]?key|secret|token|password|private[_-]?key|-----BEGIN)", re.IGNORECASE)


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _finding(rule_id: str, status: str, path: Path, root: Path, message: str, evidence: list[str] | None = None) -> ComplianceFinding:
    rule = get_rule(rule_id)
    return ComplianceFinding(
        rule_id=rule.rule_id,
        title=rule.title,
        status=status,
        severity=rule.severity if status != "pass" else "info",
        category=rule.category,
        subject=_rel(root, path),
        message=message,
        controls=list(rule.controls),
        evidence=evidence or [],
        remediation=rule.remediation,
        source="javascript",
        location=_rel(root, path),
        confidence="medium",
    )


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _load_package(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _scan_package(root: Path, package_path: Path) -> list[ComplianceFinding]:
    data = _load_package(package_path)
    if data is None:
        return []
    pkg_root = package_path.parent
    findings: list[ComplianceFinding] = []
    locks = [name for name in LOCKFILES if (pkg_root / name).exists()]
    if not locks:
        findings.append(_finding("L26-JS-002", "fail", package_path, root, "package.json exists without a lockfile"))
    elif len(locks) > 1:
        findings.append(_finding("L26-JS-002", "warn", package_path, root, f"multiple lockfiles found: {', '.join(locks)}"))
    else:
        findings.append(_finding("L26-JS-002", "pass", package_path, root, f"lockfile found: {locks[0]}"))
    engines = data.get("engines") if isinstance(data.get("engines"), dict) else {}
    node_engine = str(engines.get("node", "")).strip()
    package_manager = str(data.get("packageManager", "")).strip()
    if not node_engine or node_engine in {"*", "latest"} or node_engine.startswith(">="):
        findings.append(_finding("L26-JS-004", "warn", package_path, root, "engines.node is missing or broad"))
    if not package_manager or "@" not in package_manager:
        findings.append(_finding("L26-JS-004", "warn", package_path, root, "packageManager is missing or lacks an explicit version"))
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    lifecycle = sorted(name for name in scripts if name in LIFECYCLE_SCRIPTS)
    if lifecycle:
        findings.append(_finding("L26-JS-006", "warn", package_path, root, f"lifecycle scripts require review: {', '.join(lifecycle)}"))
    for name, value in scripts.items():
        script = str(value)
        if REMOTE_SHELL_RE.search(script):
            findings.append(_finding("L26-JS-007", "fail", package_path, root, f"script {name!r} appears to run remote shell code", [f"{name}: {script}"]))
        if "NODE_TLS_REJECT_UNAUTHORIZED=0" in script or "--inspect=0.0.0.0" in script or "--openssl-legacy-provider" in script:
            findings.append(_finding("L26-NODE-002", "fail", package_path, root, f"script {name!r} uses unsafe Node runtime flags", [f"{name}: {script}"]))
    return findings


def _scan_npmrc(root: Path, path: Path) -> list[ComplianceFinding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[ComplianceFinding] = []
    lower = text.lower()
    if "strict-ssl=false" in lower or "http://" in lower:
        findings.append(_finding("L26-JS-011", "fail", path, root, ".npmrc disables TLS validation or uses HTTP registry"))
    token_lines = [line.split("=", 1)[0] for line in text.splitlines() if "_authtoken" in line.lower() or "_auth" in line.lower() or "password" in line.lower()]
    if token_lines:
        findings.append(_finding("L26-JS-012", "fail", path, root, f"credential-like npm keys committed: {', '.join(token_lines)}"))
    return findings


def _scan_env_files(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    patterns = (".env", ".env.*", "environment*.ts", "config*.json")
    for pattern in patterns:
        for path in root.rglob(pattern):
            if _is_excluded(path) or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            risky = [line.split("=", 1)[0].strip() for line in text.splitlines() if SECRET_RE.search(line)]
            if risky:
                findings.append(_finding("L26-NODE-001", "fail", path, root, f"secret-like keys found: {', '.join(sorted(set(risky))[:5])}"))
    return findings


def _scan_angular(root: Path, path: Path) -> list[ComplianceFinding]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    findings: list[ComplianceFinding] = []
    projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
    for project_name, project in projects.items():
        if not isinstance(project, dict):
            continue
        build = ((project.get("architect") or project.get("targets") or {}).get("build") or {}) if isinstance(project.get("architect") or project.get("targets"), dict) else {}
        configs = build.get("configurations") if isinstance(build, dict) else {}
        prod = configs.get("production") if isinstance(configs, dict) else None
        if not isinstance(prod, dict):
            findings.append(_finding("L26-NG-002", "warn", path, root, f"project {project_name} lacks production build configuration"))
            continue
        if prod.get("optimization") is False or prod.get("aot") is False or prod.get("buildOptimizer") is False:
            findings.append(_finding("L26-NG-002", "fail", path, root, f"project {project_name} disables production optimization/AOT"))
        else:
            findings.append(_finding("L26-NG-002", "pass", path, root, f"project {project_name} production optimization reviewed"))
        if prod.get("sourceMap") is True or (isinstance(prod.get("sourceMap"), dict) and any(prod["sourceMap"].values())):
            findings.append(_finding("L26-NG-003", "fail", path, root, f"project {project_name} enables production source maps"))
    return findings


def _scan_angular_source(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for path in [*root.rglob("*.ts"), *root.rglob("*.html")]:
        if _is_excluded(path) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "bypassSecurityTrust" in text or "nativeElement.innerHTML" in text or "[innerHTML]" in text:
            findings.append(_finding("L26-NG-009", "warn", path, root, "Angular DOM trust bypass or innerHTML pattern requires security review"))
    return findings


def scan_javascript(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for package_path in root.rglob("package.json"):
        if not _is_excluded(package_path):
            findings.extend(_scan_package(root, package_path))
    for npmrc in root.rglob(".npmrc"):
        if not _is_excluded(npmrc):
            findings.extend(_scan_npmrc(root, npmrc))
    for angular_json in [*root.rglob("angular.json"), *root.rglob("workspace.json")]:
        if not _is_excluded(angular_json):
            findings.extend(_scan_angular(root, angular_json))
    findings.extend(_scan_env_files(root))
    findings.extend(_scan_angular_source(root))
    return findings
