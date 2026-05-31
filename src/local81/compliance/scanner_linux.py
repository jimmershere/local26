from __future__ import annotations

import stat
from pathlib import Path

from .catalog import get_rule
from .models import ComplianceFinding


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except PermissionError:
        return None, "permission_denied"
    except OSError as exc:
        return None, str(exc)


def _finding(rule_id: str, status: str, subject: str, message: str, *, root: Path, path: Path | None = None, evidence: list[str] | None = None) -> ComplianceFinding:
    rule = get_rule(rule_id)
    return ComplianceFinding(
        rule_id=rule.rule_id,
        title=rule.title,
        status=status,
        severity=rule.severity if status != "pass" else "info",
        category=rule.category,
        subject=subject,
        message=message,
        controls=list(rule.controls),
        evidence=evidence or [],
        remediation=rule.remediation,
        source="linux",
        location=_rel(root, path) if path else None,
        confidence="high" if status in {"pass", "fail"} else "medium",
    )


def _parse_assignments(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean:
            continue
        if "=" in clean:
            key, value = clean.split("=", 1)
        else:
            parts = clean.split(None, 1)
            if len(parts) != 2:
                continue
            key, value = parts
        values[key.strip().lower()] = value.strip().strip("\"'")
    return values


def _sysctl_values(root: Path) -> dict[str, tuple[str, Path]]:
    values: dict[str, tuple[str, Path]] = {}
    for path in [root / "etc/sysctl.conf", *sorted((root / "etc/sysctl.d").glob("*.conf"))]:
        if not path.is_file():
            continue
        text, _ = _read_text(path)
        if text is None:
            continue
        for key, value in _parse_assignments(text).items():
            values[key] = (value, path)
    proc_map = {
        "net.ipv4.ip_forward": root / "proc/sys/net/ipv4/ip_forward",
        "net.ipv6.conf.all.forwarding": root / "proc/sys/net/ipv6/conf/all/forwarding",
        "kernel.randomize_va_space": root / "proc/sys/kernel/randomize_va_space",
        "kernel.yama.ptrace_scope": root / "proc/sys/kernel/yama/ptrace_scope",
    }
    for key, path in proc_map.items():
        if path.is_file():
            text, _ = _read_text(path)
            if text is not None:
                values[key] = (text.strip(), path)
    return values


def _scan_inventory(root: Path) -> list[ComplianceFinding]:
    os_release = root / "etc/os-release"
    if os_release.is_file():
        text, err = _read_text(os_release)
        if text is None:
            return [_finding("L26-LNX-INV-001", "unknown", "linux inventory", f"could not read os-release: {err}", root=root, path=os_release)]
        name = next((line for line in text.splitlines() if line.startswith("PRETTY_NAME=")), "os-release present")
        return [_finding("L26-LNX-INV-001", "pass", "linux inventory", name.strip().strip("\""), root=root, path=os_release, evidence=[name])]
    return [_finding("L26-LNX-INV-001", "unknown", "linux inventory", "no os-release evidence found under scan root", root=root, path=os_release)]


def _scan_permissions(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for rel_path in ("etc/passwd", "etc/shadow", "etc/group", "etc/gshadow", "etc/sudoers", "etc/ssh/sshd_config"):
        path = root / rel_path
        if not path.exists():
            continue
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except PermissionError:
            findings.append(_finding("L26-LNX-FS-001", "unknown", rel_path, "permission denied while reading metadata", root=root, path=path))
            continue
        writable = bool(mode & stat.S_IWGRP or mode & stat.S_IWOTH)
        status = "fail" if writable else "pass"
        findings.append(_finding("L26-LNX-FS-001", status, rel_path, f"mode {mode:o}", root=root, path=path, evidence=[f"mode={mode:o}"]))
    for rel_path in ("tmp", "var/tmp", "dev/shm"):
        path = root / rel_path
        if not path.exists():
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        needs_sticky = bool(mode & stat.S_IWOTH) and not bool(mode & stat.S_ISVTX)
        findings.append(_finding("L26-LNX-FS-002", "fail" if needs_sticky else "pass", rel_path, f"mode {mode:o}", root=root, path=path, evidence=[f"mode={mode:o}"]))
    return findings


def _scan_fstab(root: Path) -> list[ComplianceFinding]:
    path = root / "etc/fstab"
    if not path.is_file():
        return []
    text, err = _read_text(path)
    if text is None:
        return [_finding("L26-LNX-MNT-001", "unknown", "temporary mounts", f"could not read fstab: {err}", root=root, path=path)]
    findings: list[ComplianceFinding] = []
    for mount_point in ("/tmp", "/var/tmp", "/dev/shm"):
        line = next((item for item in text.splitlines() if item.strip() and not item.lstrip().startswith("#") and f" {mount_point} " in item), "")
        if not line:
            findings.append(_finding("L26-LNX-MNT-001", "warn", mount_point, "no explicit fstab entry found", root=root, path=path))
            continue
        missing = [opt for opt in ("nodev", "nosuid", "noexec") if opt not in line]
        status = "fail" if missing else "pass"
        msg = f"missing options: {', '.join(missing)}" if missing else "temporary mount restrictions present"
        findings.append(_finding("L26-LNX-MNT-001", status, mount_point, msg, root=root, path=path, evidence=[line.strip()]))
    return findings


def _scan_sysctl(root: Path) -> list[ComplianceFinding]:
    values = _sysctl_values(root)
    findings: list[ComplianceFinding] = []
    for key in ("net.ipv4.ip_forward", "net.ipv6.conf.all.forwarding"):
        value_path = values.get(key)
        if not value_path:
            findings.append(_finding("L26-LNX-SYSCTL-001", "unknown", key, "no runtime or persistent evidence found", root=root))
            continue
        value, path = value_path
        findings.append(_finding("L26-LNX-SYSCTL-001", "pass" if value == "0" else "fail", key, f"value is {value}", root=root, path=path, evidence=[f"{key}={value}"]))
    redirect_keys = ("net.ipv4.conf.all.accept_redirects", "net.ipv4.conf.default.accept_redirects", "net.ipv4.conf.all.accept_source_route")
    for key in redirect_keys:
        if key in values:
            value, path = values[key]
            findings.append(_finding("L26-LNX-SYSCTL-002", "pass" if value == "0" else "fail", key, f"value is {value}", root=root, path=path, evidence=[f"{key}={value}"]))
    if "kernel.randomize_va_space" in values:
        value, path = values["kernel.randomize_va_space"]
        findings.append(_finding("L26-LNX-SYSCTL-004", "pass" if value == "2" else "fail", "kernel.randomize_va_space", f"value is {value}", root=root, path=path))
    return findings


def _scan_ssh(root: Path) -> list[ComplianceFinding]:
    path = root / "etc/ssh/sshd_config"
    if not path.is_file():
        return []
    text, err = _read_text(path)
    if text is None:
        return [_finding("L26-LNX-SSH-001", "unknown", "sshd_config", f"could not read SSH config: {err}", root=root, path=path)]
    values = _parse_assignments(text)
    findings: list[ComplianceFinding] = []
    permit_root = values.get("permitrootlogin")
    if permit_root is None:
        findings.append(_finding("L26-LNX-SSH-001", "warn", "PermitRootLogin", "directive is not explicit", root=root, path=path))
    else:
        findings.append(_finding("L26-LNX-SSH-001", "pass" if permit_root.lower() == "no" else "fail", "PermitRootLogin", f"value is {permit_root}", root=root, path=path))
    max_auth = values.get("maxauthtries")
    if max_auth:
        try:
            ok = int(max_auth) <= 4
        except ValueError:
            ok = False
        findings.append(_finding("L26-LNX-SSH-002", "pass" if ok else "fail", "MaxAuthTries", f"value is {max_auth}", root=root, path=path))
    else:
        findings.append(_finding("L26-LNX-SSH-002", "warn", "MaxAuthTries", "directive is not explicit", root=root, path=path))
    return findings


def _scan_pam_and_sudo(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    sudoers = [root / "etc/sudoers", *sorted((root / "etc/sudoers.d").glob("*"))]
    for path in sudoers:
        if not path.is_file():
            continue
        text, err = _read_text(path)
        if text is None:
            findings.append(_finding("L26-LNX-AUTH-001", "unknown", _rel(root, path), f"could not read sudoers: {err}", root=root, path=path))
            continue
        if "NOPASSWD:ALL" in text.replace(" ", "") or "ALL=(ALL) NOPASSWD" in text:
            findings.append(_finding("L26-LNX-AUTH-001", "fail", _rel(root, path), "broad NOPASSWD sudo entry found", root=root, path=path))
        elif "Defaults use_pty" in text or "logfile" in text:
            findings.append(_finding("L26-LNX-AUTH-001", "pass", _rel(root, path), "sudo audit hardening evidence found", root=root, path=path))
    pwquality = root / "etc/security/pwquality.conf"
    login_defs = root / "etc/login.defs"
    if pwquality.is_file() or login_defs.is_file():
        findings.append(_finding("L26-LNX-PAM-001", "pass", "password policy", "password policy files are present for review", root=root, path=pwquality if pwquality.is_file() else login_defs))
    return findings


def scan_linux(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    findings.extend(_scan_inventory(root))
    findings.extend(_scan_permissions(root))
    findings.extend(_scan_fstab(root))
    findings.extend(_scan_sysctl(root))
    findings.extend(_scan_ssh(root))
    findings.extend(_scan_pam_and_sudo(root))
    audit_rules = root / "etc/audit/rules.d"
    audit_conf = root / "etc/audit/auditd.conf"
    if audit_rules.exists() or audit_conf.exists():
        rule = get_rule("L26-LNX-LOG-001")
        findings.append(
            ComplianceFinding(
                rule_id=rule.rule_id,
                title=rule.title,
                status="pass",
                severity="info",
                category=rule.category,
                subject="audit configuration",
                message="audit configuration evidence is present",
                controls=list(rule.controls),
                evidence=[_rel(root, audit_conf if audit_conf.exists() else audit_rules)],
                remediation=rule.remediation,
                source="linux",
                confidence="medium",
            )
        )
    return findings
