from __future__ import annotations

from pathlib import Path

import pytest

from local81.paths import build_paths
from local81.scheduling import (
    ScheduleDef,
    ScheduleError,
    ScheduleStore,
    render_service_unit,
    render_timer_unit,
    render_wrapper,
    validate,
    validate_calendar,
    validate_name,
    validate_notify_url,
)


def _store(tmp_path: Path) -> ScheduleStore:
    return ScheduleStore(paths=build_paths(tmp_path))


def _defn(**over) -> ScheduleDef:
    base = dict(
        name="nightly-deploy",
        command=["local81", "deploy", "--latest", "--execute"],
        on_calendar="*-*-* 02:00:00",
    )
    base.update(over)
    return ScheduleDef(**base)


# --- validation ------------------------------------------------------------


def test_validate_name_rejects_bad_names() -> None:
    assert validate_name("ok-name_1") == "ok-name_1"
    for bad in ("Upper", "-leading", "has space", "with/slash", ""):
        with pytest.raises(ScheduleError):
            validate_name(bad)


def test_validate_calendar_rejects_metacharacters() -> None:
    assert validate_calendar("daily") == "daily"
    with pytest.raises(ScheduleError):
        validate_calendar("daily; rm -rf /")
    with pytest.raises(ScheduleError):
        validate_calendar("   ")


def test_validate_notify_url_requires_http() -> None:
    assert validate_notify_url(None) is None
    assert validate_notify_url("https://n8n.example/hook") == "https://n8n.example/hook"
    with pytest.raises(ScheduleError):
        validate_notify_url("ftp://nope")


def test_validate_full_defn() -> None:
    assert validate(_defn()) is not None


# --- rendering -------------------------------------------------------------


def test_wrapper_uses_flock_no_overlap(tmp_path: Path) -> None:
    lock = tmp_path / "n.lock"
    text = render_wrapper(_defn(), lock_path=lock)
    assert text.startswith("#!/bin/sh")
    assert f"flock -n {lock}" in text
    assert "local81 deploy --latest --execute" in text


def test_wrapper_quotes_command_parts() -> None:
    text = render_wrapper(_defn(command=["sh", "-c", "echo hi there"]), lock_path=Path("/l"))
    assert "'echo hi there'" in text


def test_service_unit_has_oneshot_and_execstart(tmp_path: Path) -> None:
    wrapper = tmp_path / "w.sh"
    text = render_service_unit(_defn(), wrapper_path=wrapper)
    assert "Type=oneshot" in text
    assert f"ExecStart={wrapper}" in text
    assert "ExecStartPost" not in text  # no notify_url => no curl line


def test_service_unit_adds_notify_post() -> None:
    text = render_service_unit(_defn(notify_url="https://n8n.example/hook"), wrapper_path=Path("/w"))
    assert "ExecStartPost=" in text
    assert "curl" in text
    assert "https://n8n.example/hook" in text
    assert "|| true" in text  # best-effort, never fails the run


def test_timer_unit_has_oncalendar_and_install() -> None:
    text = render_timer_unit(_defn())
    assert "OnCalendar=*-*-* 02:00:00" in text
    assert "WantedBy=timers.target" in text
    assert "Persistent=true" in text


# --- store roundtrip -------------------------------------------------------


def test_store_save_writes_def_wrapper_and_units(tmp_path: Path) -> None:
    store = _store(tmp_path)
    written = store.save(_defn())
    names = {p.name for p in written}
    assert "nightly-deploy.json" in names
    assert "local81-nightly-deploy.sh" in names
    assert "local81-nightly-deploy.service" in names
    assert "local81-nightly-deploy.timer" in names
    # wrapper is executable; def + units are owner-only
    assert (store.wrapper_path("nightly-deploy").stat().st_mode & 0o777) == 0o700
    assert (store.def_path("nightly-deploy").stat().st_mode & 0o777) == 0o600


def test_store_list_and_load_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_defn())
    store.save(_defn(name="weekly", on_calendar="weekly"))
    listed = {d.name for d in store.list()}
    assert listed == {"nightly-deploy", "weekly"}
    loaded = store.load("nightly-deploy")
    assert loaded.command == ["local81", "deploy", "--latest", "--execute"]


def test_store_remove_deletes_all_files(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_defn())
    removed = store.remove("nightly-deploy")
    assert len(removed) == 4
    assert store.list() == []


def test_store_remove_unknown_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ScheduleError):
        store.remove("ghost")


def test_store_save_rejects_invalid_name(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ScheduleError):
        store.save(_defn(name="Bad Name"))
