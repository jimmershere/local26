from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from seraf.config import load_config


def _format_pull_command(*, host: str, target_dir: Path, source_dir: Path, rsync_opts: str) -> str:
    parts = ["rsync", *shlex.split(rsync_opts), "--", f"{host}:{target_dir.as_posix().rstrip('/')}/", f"{source_dir.as_posix().rstrip('/')}/"]
    return shlex.join(parts)


def run_pull(*, scope: str | None = None, hosts: str | None = None,
             rsync_opts: str | None = None, dry_run: bool = False,
             profile: str | None = None) -> int:
    config = load_config(profile=profile)
    selected_scopes = [s for s in config.scopes if scope is None or s.name == scope]
    if not selected_scopes:
        print("seraf: no matching scopes found")
        return 1

    success_count = 0
    failed_count = 0

    for scope_config in selected_scopes:
        if not scope_config.enabled:
            print(f"[pull] scope={scope_config.name} skipped (disabled)")
            continue

        effective_hosts = [h.strip() for h in (hosts.split(",") if hosts else scope_config.servers) if h.strip()]
        if not scope_config.source_dir or not scope_config.target_dir or not effective_hosts:
            print(f"seraf: warning: scope={scope_config.name} skipped (needs source_dir, target_dir, and servers/--hosts)")
            continue

        scope_config.source_dir.mkdir(parents=True, exist_ok=True)
        effective_rsync_opts = rsync_opts or scope_config.rsync_opts or config.default_rsync_opts

        for host in effective_hosts:
            command = _format_pull_command(
                host=host,
                target_dir=scope_config.target_dir,
                source_dir=scope_config.source_dir,
                rsync_opts=effective_rsync_opts,
            )
            if dry_run:
                print(f"[pull] dry-run scope={scope_config.name} host={host} cmd={command}")
                success_count += 1
                continue

            proc = subprocess.run(command, shell=True, text=True)
            if proc.returncode == 0:
                print(f"[pull] scope={scope_config.name} host={host} ok")
                success_count += 1
            else:
                print(f"seraf: warning: scope={scope_config.name} host={host} failed")
                failed_count += 1

    print(f"Pulled files into local source dirs (success={success_count}, failed={failed_count})")
    return 0 if failed_count == 0 else 1
