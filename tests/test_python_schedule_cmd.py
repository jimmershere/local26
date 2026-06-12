from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from local81.commands.schedule import run_schedule
from local81.paths import build_paths
from local81.scheduling import ScheduleStore


def _args(monkeypatch, tmp_path: Path, **kw) -> Namespace:
    # run_schedule builds its own ScheduleStore() rooted at cwd, so chdir there.
    monkeypatch.chdir(tmp_path)
    base = dict(
        name=None,
        command_str=None,
        on_calendar=None,
        notify_url=None,
        description=None,
        working_dir=None,
    )
    base.update(kw)
    return Namespace(**base)


def test_add_then_list_then_remove(monkeypatch, tmp_path: Path, capsys) -> None:
    rc = run_schedule(_args(
        monkeypatch, tmp_path,
        schedule_command="add",
        name="nightly",
        command_str="local81 deploy --latest --execute",
        on_calendar="*-*-* 02:00:00",
        notify_url="https://n8n.example/hook",
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Added schedule 'nightly'" in out
    assert "systemctl daemon-reload" in out  # install hint shown

    store = ScheduleStore(paths=build_paths(tmp_path))
    assert {d.name for d in store.list()} == {"nightly"}
    assert store.service_path("nightly").exists()

    rc = run_schedule(_args(monkeypatch, tmp_path, schedule_command="list"))
    assert rc == 0
    assert "nightly" in capsys.readouterr().out

    rc = run_schedule(_args(monkeypatch, tmp_path, schedule_command="remove", name="nightly"))
    assert rc == 0
    assert "Removed schedule 'nightly'" in capsys.readouterr().out
    assert store.list() == []


def test_add_rejects_bad_calendar(monkeypatch, tmp_path: Path, capsys) -> None:
    rc = run_schedule(_args(
        monkeypatch, tmp_path,
        schedule_command="add",
        name="bad",
        command_str="echo hi",
        on_calendar="daily; rm -rf /",
    ))
    assert rc == 1
    assert "cannot add schedule" in capsys.readouterr().out


def test_add_rejects_empty_command(monkeypatch, tmp_path: Path, capsys) -> None:
    rc = run_schedule(_args(
        monkeypatch, tmp_path,
        schedule_command="add",
        name="empty",
        command_str="   ",
        on_calendar="daily",
    ))
    assert rc == 1
    assert "must not be empty" in capsys.readouterr().out


def test_list_empty_is_friendly(monkeypatch, tmp_path: Path, capsys) -> None:
    rc = run_schedule(_args(monkeypatch, tmp_path, schedule_command="list"))
    assert rc == 0
    assert "No schedules defined" in capsys.readouterr().out


def test_doctor_reports_counts(monkeypatch, tmp_path: Path, capsys) -> None:
    run_schedule(_args(
        monkeypatch, tmp_path,
        schedule_command="add", name="nightly",
        command_str="echo hi", on_calendar="daily",
    ))
    capsys.readouterr()
    rc = run_schedule(_args(monkeypatch, tmp_path, schedule_command="doctor"))
    out = capsys.readouterr().out
    assert "schedule doctor" in out
    assert "schedules:count: 1 defined" in out
    assert rc == 0
