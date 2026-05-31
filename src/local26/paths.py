from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Local26Paths:
    root: Path
    local26_dir: Path
    config_file: Path
    lock_file: Path
    state_dir: Path
    plans_dir: Path
    runs_dir: Path
    logs_dir: Path
    artifacts_dir: Path
    reports_dir: Path
    captures_dir: Path
    hooks_dir: Path
    profiles_dir: Path


def build_paths(root: str | Path = ".") -> Local26Paths:
    root_path = Path(root).resolve()
    local26_dir = root_path / ".local26"
    return Local26Paths(
        root=root_path,
        local26_dir=local26_dir,
        config_file=local26_dir / "config.ini",
        lock_file=local26_dir / "local26.lock",
        state_dir=local26_dir / "state",
        plans_dir=local26_dir / "plans",
        runs_dir=local26_dir / "runs",
        logs_dir=local26_dir / "logs",
        artifacts_dir=local26_dir / "artifacts",
        reports_dir=local26_dir / "reports",
        captures_dir=local26_dir / "captures",
        hooks_dir=local26_dir / "hooks",
        profiles_dir=local26_dir / "profiles",
    )


def ensure_runtime_dirs(root: str | Path = ".") -> Local26Paths:
    paths = build_paths(root)
    for path in [
        paths.local26_dir,
        paths.state_dir,
        paths.plans_dir,
        paths.runs_dir,
        paths.logs_dir,
        paths.artifacts_dir,
        paths.reports_dir,
        paths.captures_dir,
        paths.hooks_dir,
        paths.profiles_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    return paths
