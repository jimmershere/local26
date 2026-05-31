from __future__ import annotations

import csv
import subprocess
from pathlib import Path

DIAG_TYPE_STRACE = "strace"
DIAG_TYPE_PYSPY = "py-spy"
DIAG_TYPE_AUSTIN = "austin"

_DIAG_HOSTS_M2_PROJECT = [
    ("10.242.225.11", "a70lscomm2ap001", "cmsap1", False),
    ("10.242.249.11", "a70lscomm2db001", "cmsdb1", False),
    ("10.242.209.11", "a70lscomm2pr001", "cmspr1", False),
    ("192.168.147.23", "a70lppalutil001", "util", False),
    ("10.242.9.13", "a70lpcomm2pr001", "cmppr1", True),
    ("10.242.9.14", "a70lpcomm2pr002", "cmppr2", True),
    ("10.242.9.15", "a70lpcomm2pr003", "cmppr3", False),
    ("10.242.25.27", "a70lpcomm2ap001", "cmpap1", False),
    ("10.242.25.28", "a70lpcomm2ap002", "cmpap2", False),
    ("10.242.25.35", "a70lpcomm2cm001", "cmpcm1", True),
    ("10.242.25.31", "a70lpcomm2tr001", "cmptr1", True),
    ("10.242.25.32", "a70lpcomm2tr002", "cmptr2", True),
    ("10.242.25.33", "a70lpcomm2tr003", "cmptr3", True),
    ("10.242.25.34", "a70lpcomm2tr004", "cmppr4", True),
    ("10.242.41.12", "a70lpcomm2db001", "cmpdb1", True),
    ("10.242.41.13", "a70lpcomm2db002", "cmpdb2", True),
    ("10.242.9.11", "a70lqcomm2pr001", "cmqpr1", False),
    ("10.242.9.12", "a70lqcomm2pr002", "cmqpr2", True),
    ("10.242.25.15", "a70lqcomm2ap001", "cmqap1", False),
    ("10.242.25.16", "a70lqcomm2ap002", "cmqap2", False),
    ("10.242.25.19", "a70lqcomm2cm001", "cmqcm1", False),
    ("10.242.25.17", "a70lqcomm2tr001", "cmqtr1", False),
    ("10.242.25.18", "a70lqcomm2tr002", "cmqtr2", False),
    ("10.242.41.11", "a70lqcomm2db001", "cmqdb1", True),
    ("10.242.225.13", "a70lscomm2cm001", "cmscm1", True),
    ("10.242.225.12", "a70lscomm2tr001", "cmstr1", True),
    ("10.243.9.14", "a70lppalm2ex001", "pex1", False),
    ("10.243.9.15", "a70lppalm2ex002", "pex2", False),
    ("10.243.9.16", "a70lppalm2ex003", "pex3", False),
    ("10.243.25.15", "a70lppalm2in001", "pin1", False),
    ("10.243.25.16", "a70lppalm2in002", "pin2", False),
    ("10.243.25.19", "a70lppalm2tr001", "ediptr1", False),
    ("10.243.25.20", "a70lppalm2tr002", "ediptr2", False),
    ("10.243.25.21", "a70lppalm2tr003", "ediptr3", False),
    ("10.243.25.22", "a70lppalm2tr004", "ediptr4", False),
    ("10.243.25.23", "a70lppalm2tr005", "ediptr5", False),
    ("10.243.25.24", "a70lppalm2tr006", "ediptr6", False),
    ("10.243.41.11", "a70lppalm2or001", "por1", False),
    ("10.243.41.14", "a70lppalm2or002", "por2", False),
    ("10.243.9.11", "a70lqpalm2ex001", "qex1", False),
    ("10.243.9.12", "a70lqpalm2ex002", "qex2", False),
    ("10.243.9.13", "a70lqpalm2ex003", "qex3", False),
    ("10.243.25.13", "a70lqpalm2in001", "qin1", False),
    ("10.243.25.14", "a70lqpalm2in002", "qin2", False),
    ("10.243.25.17", "a70lqpalm2tr001", "ediqtr1", False),
    ("10.243.25.18", "a70lqpalm2tr002", "ediqtr2", False),
    ("10.243.41.12", "a70lqpalm2or001", "qor1", False),
    ("10.243.209.11", "a70lspalm2ex001", "sex1", False),
    ("10.243.225.11", "a70lspalm2in001", "sin1", False),
    ("10.243.225.13", "a70lspalm2tr001", "edistr1", False),
    ("10.243.241.11", "a70lspalm2or001", "sor1", False),
]


def resolve_diag_hosts_for_project(project: str, hosts_csv: str | None = None, *, include_disabled: bool = False) -> str:
    if project != "m2-project":
        raise ValueError(f"unsupported diag project inventory: {project}")

    inventory = _DIAG_HOSTS_M2_PROJECT
    tokens = [t.strip() for t in (hosts_csv or "all").split(",") if t.strip()]
    if not tokens:
        tokens = ["all"]

    resolved: list[str] = []
    for token in tokens:
        if token == "all":
            for ip, _host, _alias, disabled in inventory:
                if disabled and not include_disabled:
                    continue
                if ip not in resolved:
                    resolved.append(ip)
            continue

        match = None
        for ip, host, alias, disabled in inventory:
            if disabled and not include_disabled:
                continue
            if token in {ip, host, alias}:
                match = ip
                break
        if not match:
            raise ValueError(f"unknown or disabled host token for project {project}: {token}")
        if match not in resolved:
            resolved.append(match)

    return ",".join(resolved)


def diag_remote_command_for_type(diag_type: str, pid: str, duration: str) -> str:
    if diag_type == DIAG_TYPE_STRACE:
        return f"timeout {duration} strace -f -tt -s 256 -p {pid}"
    if diag_type == DIAG_TYPE_PYSPY:
        return f"timeout {duration} py-spy dump --pid {pid} --native --locals"
    if diag_type == DIAG_TYPE_AUSTIN:
        return f"timeout {duration} austin -Cp {pid}"
    raise ValueError(
        f"unsupported diag type: {diag_type} (supported: {DIAG_TYPE_STRACE}, {DIAG_TYPE_PYSPY}, {DIAG_TYPE_AUSTIN})"
    )


def run_diag(*, project: str | None = None, hosts: str | None = None,
             diag_type: str = DIAG_TYPE_STRACE, pid: str | None = None,
             duration: str = "20s", remote_cmd: str | None = None,
             out_dir: str | None = None, ssh_user: str | None = None,
             include_disabled: bool = False, dry_run: bool = False) -> int:
    if remote_cmd and pid:
        print("local81: use either --remote-cmd or --pid/--diag-type, not both")
        return 2

    if not remote_cmd:
        if not pid:
            print("local81: --pid is required unless --remote-cmd is provided")
            return 2
        try:
            remote_cmd = diag_remote_command_for_type(diag_type, pid, duration)
        except ValueError as exc:
            print(f"local81: {exc}")
            return 1

    if project:
        try:
            hosts = resolve_diag_hosts_for_project(project, hosts, include_disabled=include_disabled)
        except ValueError as exc:
            print(f"local81: {exc}")
            return 1

    host_list = [h.strip() for h in (hosts or "").split(",") if h.strip()]
    if not host_list:
        print("local81: no hosts provided; use --hosts CSV or --project NAME")
        return 2

    output_dir = Path(out_dir) if out_dir else Path(".local81") / "diag" / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "diag-run.tsv"
    overall_rc = 0
    rows: list[list[str]] = []

    for host in host_list:
        ssh_target = f"{ssh_user}@{host}" if ssh_user else host
        stdout_path = output_dir / f"{host}.stdout.log"
        stderr_path = output_dir / f"{host}.stderr.log"
        rc = 0

        if dry_run:
            stdout_path.write_text(f"dry-run ssh {ssh_target} {remote_cmd}\n", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
        else:
            proc = subprocess.run(["ssh", ssh_target, remote_cmd], capture_output=True, text=True)
            stdout_path.write_text(proc.stdout, encoding="utf-8")
            stderr_path.write_text(proc.stderr, encoding="utf-8")
            rc = proc.returncode
            if rc != 0:
                overall_rc = rc

        rows.append([host, str(rc), str(stdout_path), str(stderr_path), remote_cmd])
        print(f"[diag] host={host} rc={rc} stdout={stdout_path} stderr={stderr_path}")

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["host", "rc", "stdout", "stderr", "cmd"])
        writer.writerows(rows)

    print(f"[diag] manifest={manifest_path}")
    return overall_rc
