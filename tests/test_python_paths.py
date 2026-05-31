from __future__ import annotations

from pathlib import Path

from local26.paths import build_paths, ensure_runtime_dirs


def test_build_paths_layout(tmp_path: Path) -> None:
    paths = build_paths(tmp_path)
    assert paths.root == tmp_path.resolve()
    assert paths.local26_dir == tmp_path.resolve() / ".local26"
    assert paths.config_file == tmp_path.resolve() / ".local26" / "config.ini"
    assert paths.reports_dir == tmp_path.resolve() / ".local26" / "reports"
    assert paths.hooks_dir == tmp_path.resolve() / ".local26" / "hooks"
    assert paths.profiles_dir == tmp_path.resolve() / ".local26" / "profiles"


def test_ensure_runtime_dirs_creates_layout(tmp_path: Path) -> None:
    paths = ensure_runtime_dirs(tmp_path)
    assert paths.local26_dir.is_dir()
    assert paths.state_dir.is_dir()
    assert paths.plans_dir.is_dir()
    assert paths.runs_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.artifacts_dir.is_dir()
    assert paths.reports_dir.is_dir()
    assert paths.captures_dir.is_dir()
    assert paths.hooks_dir.is_dir()
    assert paths.profiles_dir.is_dir()
