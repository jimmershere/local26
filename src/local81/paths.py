from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Local81Paths:
    root: Path
    local81_dir: Path
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
    schedules_dir: Path


def build_paths(root: str | Path = ".") -> Local81Paths:
    root_path = Path(root).resolve()
    local81_dir = root_path / ".local81"
    return Local81Paths(
        root=root_path,
        local81_dir=local81_dir,
        config_file=local81_dir / "config.ini",
        lock_file=local81_dir / "local81.lock",
        state_dir=local81_dir / "state",
        plans_dir=local81_dir / "plans",
        runs_dir=local81_dir / "runs",
        logs_dir=local81_dir / "logs",
        artifacts_dir=local81_dir / "artifacts",
        reports_dir=local81_dir / "reports",
        captures_dir=local81_dir / "captures",
        hooks_dir=local81_dir / "hooks",
        profiles_dir=local81_dir / "profiles",
        schedules_dir=local81_dir / "schedules",
    )


def ensure_runtime_dirs(root: str | Path = ".") -> Local81Paths:
    paths = build_paths(root)
    for path in [
        paths.local81_dir,
        paths.state_dir,
        paths.plans_dir,
        paths.runs_dir,
        paths.logs_dir,
        paths.artifacts_dir,
        paths.reports_dir,
        paths.captures_dir,
        paths.hooks_dir,
        paths.profiles_dir,
        paths.schedules_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    return paths
