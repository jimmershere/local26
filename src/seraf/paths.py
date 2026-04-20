from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SerafPaths:
    root: Path
    seraf_dir: Path
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


def build_paths(root: str | Path = ".") -> SerafPaths:
    root_path = Path(root).resolve()
    seraf_dir = root_path / ".seraf"
    return SerafPaths(
        root=root_path,
        seraf_dir=seraf_dir,
        config_file=seraf_dir / "config.ini",
        lock_file=seraf_dir / "seraf.lock",
        state_dir=seraf_dir / "state",
        plans_dir=seraf_dir / "plans",
        runs_dir=seraf_dir / "runs",
        logs_dir=seraf_dir / "logs",
        artifacts_dir=seraf_dir / "artifacts",
        reports_dir=seraf_dir / "reports",
        captures_dir=seraf_dir / "captures",
        hooks_dir=seraf_dir / "hooks",
        profiles_dir=seraf_dir / "profiles",
    )


def ensure_runtime_dirs(root: str | Path = ".") -> SerafPaths:
    paths = build_paths(root)
    for path in [
        paths.seraf_dir,
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
    return paths
