from __future__ import annotations

import local81.cli as cli


def test_main_dispatches_history(monkeypatch) -> None:
    called: dict[str, int] = {}

    def fake_run_history(*, limit: int) -> int:
        called["limit"] = limit
        return 17

    monkeypatch.setattr(cli, "run_history", fake_run_history)
    monkeypatch.setattr("sys.argv", ["local81", "history", "--limit", "7"])

    assert cli.main() == 17
    assert called == {"limit": 7}


def test_main_dispatches_logs(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_logs(run_id: str, *, host: str | None = None) -> int:
        called["run_id"] = run_id
        called["host"] = host
        return 9

    monkeypatch.setattr(cli, "run_logs", fake_run_logs)
    monkeypatch.setattr("sys.argv", ["local81", "logs", "run-123"])

    assert cli.main() == 9
    assert called == {"run_id": "run-123", "host": None}


def test_main_dispatches_hooks(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_hooks", lambda: 5)
    monkeypatch.setattr("sys.argv", ["local81", "hooks"])
    assert cli.main() == 5


def test_main_dispatches_profiles(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_profiles", lambda: 6)
    monkeypatch.setattr("sys.argv", ["local81", "profiles"])
    assert cli.main() == 6


def test_main_dispatches_profile_create(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_profile_create(name: str) -> int:
        called["name"] = name
        return 4

    monkeypatch.setattr(cli, "run_profile_create", fake_run_profile_create)
    monkeypatch.setattr("sys.argv", ["local81", "profile", "create", "prod"])

    assert cli.main() == 4
    assert called == {"name": "prod"}


def test_main_dispatches_guided_init(monkeypatch) -> None:
    called: dict[str, bool] = {}

    def fake_run_guided(*, force: bool) -> int:
        called["force"] = force
        return 8

    monkeypatch.setattr(cli, "run_guided", fake_run_guided)
    monkeypatch.setattr("sys.argv", ["local81", "init", "--guided", "--force"])

    assert cli.main() == 8
    assert called == {"force": True}


def test_main_dispatches_db_doctor(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_db(args) -> int:
        called["command"] = args.db_command
        called["target"] = args.target
        return 12

    monkeypatch.setattr(cli, "run_db", fake_run_db)
    monkeypatch.setattr("sys.argv", ["local81", "db", "doctor", "--target", "main"])

    assert cli.main() == 12
    assert called == {"command": "doctor", "target": "main"}


def test_main_dispatches_schedule_add(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_schedule(args) -> int:
        called["command"] = args.schedule_command
        called["name"] = args.name
        called["on_calendar"] = args.on_calendar
        return 11

    monkeypatch.setattr(cli, "run_schedule", fake_run_schedule)
    monkeypatch.setattr(
        "sys.argv",
        ["local81", "schedule", "add", "nightly", "--command", "local81 deploy --latest", "--on-calendar", "daily"],
    )

    assert cli.main() == 11
    assert called == {"command": "add", "name": "nightly", "on_calendar": "daily"}


def test_main_dispatches_schedule_doctor(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_schedule(args) -> int:
        called["command"] = args.schedule_command
        return 3

    monkeypatch.setattr(cli, "run_schedule", fake_run_schedule)
    monkeypatch.setattr("sys.argv", ["local81", "schedule", "doctor"])

    assert cli.main() == 3
    assert called == {"command": "doctor"}


def test_main_dispatches_rollback(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run_rollback(run_id: str, *, execute: bool = False) -> int:
        called["run_id"] = run_id
        called["execute"] = execute
        return 21

    monkeypatch.setattr(cli, "run_rollback", fake_run_rollback)
    monkeypatch.setattr("sys.argv", ["local81", "rollback", "run-9", "--execute"])

    assert cli.main() == 21
    assert called == {"run_id": "run-9", "execute": True}


def test_main_dispatches_rollback_dry_run(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run_rollback(run_id: str, *, execute: bool = False) -> int:
        called["run_id"] = run_id
        called["execute"] = execute
        return 0

    monkeypatch.setattr(cli, "run_rollback", fake_run_rollback)
    monkeypatch.setattr("sys.argv", ["local81", "rollback", "run-9"])

    assert cli.main() == 0
    assert called == {"run_id": "run-9", "execute": False}


def test_main_dispatches_gc(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run_gc(*, keep, max_age_days, execute) -> int:
        called["keep"] = keep
        called["max_age_days"] = max_age_days
        called["execute"] = execute
        return 22

    monkeypatch.setattr(cli, "run_gc", fake_run_gc)
    monkeypatch.setattr(
        "sys.argv",
        ["local81", "gc", "--keep", "5", "--max-age-days", "30", "--execute"],
    )

    assert cli.main() == 22
    assert called == {"keep": 5, "max_age_days": 30, "execute": True}


def test_main_dispatches_gc_defaults(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run_gc(*, keep, max_age_days, execute) -> int:
        called["keep"] = keep
        called["max_age_days"] = max_age_days
        called["execute"] = execute
        return 0

    monkeypatch.setattr(cli, "run_gc", fake_run_gc)
    monkeypatch.setattr("sys.argv", ["local81", "gc"])

    assert cli.main() == 0
    assert called == {"keep": None, "max_age_days": None, "execute": False}


def test_main_dispatches_compliance_harden_plan(monkeypatch) -> None:
    called: dict[str, str] = {}

    def fake_run_compliance(args) -> int:
        called["command"] = args.compliance_command
        called["scope"] = args.scope
        called["format"] = args.format
        return 13

    monkeypatch.setattr(cli, "run_compliance", fake_run_compliance)
    monkeypatch.setattr("sys.argv", ["local81", "compliance", "harden-plan", "--scope", "linux", "--format", "json"])

    assert cli.main() == 13
    assert called == {"command": "harden-plan", "scope": "linux", "format": "json"}
