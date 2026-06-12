"""Read-only shell probes and their pure parsers.

Each fact is split into three pieces so they are independently testable:

* a ``*_probe`` builder that returns the argv to execute (paths/names are
  ``shlex.quote``-escaped to avoid injection),
* a ``parse_*`` pure function that turns probe stdout into a typed dataclass,
* a public ``*_state`` / ``*_probe`` function that runs the probe via a
  :class:`~local81.connectors.Connector` and parses the result.

Probes target GNU coreutils / systemd (Linux), matching Local-81's documented
runtime requirements (``stat``, ``sha256sum``, ``systemctl``, ``dpkg``/``rpm``).
"""

from __future__ import annotations

import shlex

from ..connectors import Connector
from .models import CommandProbe, DirState, FileState, PackageState, ServiceState


def _kv(stdout: str) -> dict[str, str]:
    """Parse ``key=value`` probe lines into a dict (last write wins)."""
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


# --------------------------------------------------------------------------- #
# file_state
# --------------------------------------------------------------------------- #
def file_state_probe(path: str) -> list[str]:
    q = shlex.quote(path)
    script = (
        f"p={q}\n"
        'if [ -e "$p" ]; then\n'
        '  echo "exists=1"\n'
        '  if [ -f "$p" ]; then echo "is_file=1"; else echo "is_file=0"; fi\n'
        "  echo \"meta=$(stat -c '%a|%U|%G|%s' -- \"$p\" 2>/dev/null)\"\n"
        '  if [ -f "$p" ]; then echo "sha256=$(sha256sum -- "$p" 2>/dev/null | cut -d" " -f1)"; fi\n'
        "else\n"
        '  echo "exists=0"\n'
        "fi\n"
    )
    return ["sh", "-c", script]


def parse_file_state(path: str, stdout: str) -> FileState:
    kv = _kv(stdout)
    if kv.get("exists") != "1":
        return FileState(path=path, exists=False)
    mode = owner = group = None
    size: int | None = None
    meta = kv.get("meta", "")
    if meta:
        parts = meta.split("|")
        if len(parts) == 4:
            mode, owner, group, raw_size = parts
            size = int(raw_size) if raw_size.isdigit() else None
    sha = kv.get("sha256") or None
    return FileState(
        path=path,
        exists=True,
        is_file=kv.get("is_file") == "1",
        mode=mode or None,
        owner=owner or None,
        group=group or None,
        size=size,
        sha256=sha,
    )


def file_state(conn: Connector, path: str, *, timeout_seconds: int | None = None) -> FileState:
    result = conn.run(file_state_probe(path), timeout_seconds=timeout_seconds)
    return parse_file_state(path, result.stdout)


# --------------------------------------------------------------------------- #
# dir_state
# --------------------------------------------------------------------------- #
def dir_state_probe(path: str) -> list[str]:
    q = shlex.quote(path)
    script = (
        f"p={q}\n"
        'if [ -d "$p" ]; then\n'
        '  echo "exists=1"; echo "is_dir=1"\n'
        "  echo \"meta=$(stat -c '%a|%U|%G' -- \"$p\" 2>/dev/null)\"\n"
        'elif [ -e "$p" ]; then\n'
        '  echo "exists=1"; echo "is_dir=0"\n'
        "  echo \"meta=$(stat -c '%a|%U|%G' -- \"$p\" 2>/dev/null)\"\n"
        "else\n"
        '  echo "exists=0"; echo "is_dir=0"\n'
        "fi\n"
    )
    return ["sh", "-c", script]


def parse_dir_state(path: str, stdout: str) -> DirState:
    kv = _kv(stdout)
    if kv.get("exists") != "1":
        return DirState(path=path, exists=False)
    mode = owner = group = None
    meta = kv.get("meta", "")
    if meta:
        parts = meta.split("|")
        if len(parts) == 3:
            mode, owner, group = parts
    return DirState(
        path=path,
        exists=True,
        is_dir=kv.get("is_dir") == "1",
        mode=mode or None,
        owner=owner or None,
        group=group or None,
    )


def dir_state(conn: Connector, path: str, *, timeout_seconds: int | None = None) -> DirState:
    result = conn.run(dir_state_probe(path), timeout_seconds=timeout_seconds)
    return parse_dir_state(path, result.stdout)


# --------------------------------------------------------------------------- #
# service_state
# --------------------------------------------------------------------------- #
_SERVICE_PRESENT_STATES = {"active", "inactive", "activating", "deactivating", "failed", "reloading"}


def service_state_probe(name: str) -> list[str]:
    q = shlex.quote(name)
    script = (
        f"n={q}\n"
        'echo "active=$(systemctl is-active -- "$n" 2>/dev/null)"\n'
        'echo "enabled=$(systemctl is-enabled -- "$n" 2>/dev/null)"\n'
    )
    return ["sh", "-c", script]


def parse_service_state(name: str, stdout: str) -> ServiceState:
    kv = _kv(stdout)
    raw_active = kv.get("active", "")
    raw_enabled = kv.get("enabled", "")
    present = raw_active in _SERVICE_PRESENT_STATES or raw_enabled in {"enabled", "disabled", "static", "masked"}
    return ServiceState(
        name=name,
        present=present,
        active=raw_active == "active",
        enabled=raw_enabled == "enabled",
        raw_active=raw_active,
        raw_enabled=raw_enabled,
    )


def service_state(conn: Connector, name: str, *, timeout_seconds: int | None = None) -> ServiceState:
    result = conn.run(service_state_probe(name), timeout_seconds=timeout_seconds)
    return parse_service_state(name, result.stdout)


# --------------------------------------------------------------------------- #
# package_state
# --------------------------------------------------------------------------- #
def package_state_probe(name: str) -> list[str]:
    q = shlex.quote(name)
    script = (
        f"n={q}\n"
        "if command -v dpkg-query >/dev/null 2>&1; then\n"
        '  echo "manager=dpkg"\n'
        "  echo \"result=$(dpkg-query -W -f='${Status}|${Version}' -- \"$n\" 2>/dev/null)\"\n"
        "elif command -v rpm >/dev/null 2>&1; then\n"
        '  echo "manager=rpm"\n'
        "  echo \"result=$(rpm -q --qf '%{VERSION}-%{RELEASE}' -- \"$n\" 2>/dev/null)\"\n"
        "else\n"
        '  echo "manager=none"\n'
        "fi\n"
    )
    return ["sh", "-c", script]


def parse_package_state(name: str, stdout: str) -> PackageState:
    kv = _kv(stdout)
    manager = kv.get("manager", "none")
    result = kv.get("result", "")
    if manager == "dpkg":
        status, _, version = result.partition("|")
        installed = status.strip() == "install ok installed"
        return PackageState(name=name, installed=installed, version=version or None if installed else None, manager=manager)
    if manager == "rpm":
        installed = bool(result) and "is not installed" not in result
        return PackageState(name=name, installed=installed, version=result or None if installed else None, manager=manager)
    return PackageState(name=name, installed=False, version=None, manager="none")


def package_state(conn: Connector, name: str, *, timeout_seconds: int | None = None) -> PackageState:
    result = conn.run(package_state_probe(name), timeout_seconds=timeout_seconds)
    return parse_package_state(name, result.stdout)


# --------------------------------------------------------------------------- #
# command_probe (arbitrary read-only check for runbook guards)
# --------------------------------------------------------------------------- #
def command_probe(conn: Connector, command: str | list[str], *, timeout_seconds: int | None = None) -> CommandProbe:
    result = conn.run(command, timeout_seconds=timeout_seconds)
    return CommandProbe(
        command=result.command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
