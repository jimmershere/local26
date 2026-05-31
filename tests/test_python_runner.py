from __future__ import annotations

import pytest

from local26.runner import RunnerError, run_local, run_remote


def test_run_local_success() -> None:
    result = run_local(["python3", "-c", "print('ok')"])
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
    assert result.stderr == ""
    assert result.dry_run is False


def test_run_local_dry_run() -> None:
    result = run_local("echo hello", dry_run=True)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.dry_run is True
    assert result.command == ["echo", "hello"]


def test_run_local_check_raises() -> None:
    with pytest.raises(RunnerError):
        run_local(["python3", "-c", "import sys; sys.exit(5)"], check=True)


def test_run_remote_dry_run_wraps_ssh() -> None:
    result = run_remote("example-host", "echo hi", dry_run=True)
    assert result.returncode == 0
    assert result.dry_run is True
    assert result.command[0] == "ssh"
    assert result.command[1] == "example-host"
    assert "echo hi" in result.command[2]
