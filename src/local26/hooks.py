from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

HOOK_NAMES = ("pre-deploy.sh", "post-deploy.sh")


@dataclass(slots=True)
class HookStatus:
    name: str
    path: Path
    exists: bool
    executable: bool


def hook_dir(root: str | Path = ".") -> Path:
    return Path(root) / ".local26" / "hooks"


def list_hooks(root: str | Path = ".") -> list[HookStatus]:
    base = hook_dir(root)
    statuses: list[HookStatus] = []
    for name in HOOK_NAMES:
        path = base / name
        statuses.append(HookStatus(name=name, path=path, exists=path.exists(), executable=os.access(path, os.X_OK)))
    return statuses


def run_hook(name: str, *, env: dict[str, str] | None = None, root: str | Path = ".") -> tuple[int, str, str]:
    path = hook_dir(root) / name
    if not path.exists():
        return 0, "", ""
    proc = subprocess.run(["bash", str(path)], text=True, capture_output=True, env=env)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
