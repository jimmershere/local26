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

    def fake_run_logs(run_id: str) -> int:
        called["run_id"] = run_id
        return 9

    monkeypatch.setattr(cli, "run_logs", fake_run_logs)
    monkeypatch.setattr("sys.argv", ["local81", "logs", "run-123"])

    assert cli.main() == 9
    assert called == {"run_id": "run-123"}


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
