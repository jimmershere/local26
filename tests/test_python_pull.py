from __future__ import annotations

from pathlib import Path

from local81.commands.pull import _format_pull_command, run_pull


CONFIG_TEMPLATE = """[local81]
version = 0.1
project = test

[defaults]
rsync_opts = -az

[scope \"app\"]
enabled = true
source_dir = {app_source}
target_dir = /srv/app
servers = old1,old2

[scope \"api\"]
enabled = true
source_dir = {api_source}
target_dir = /srv/api
servers = api1

[scope \"disabled\"]
enabled = false
source_dir = {disabled_source}
target_dir = /srv/disabled
servers = disabled1
"""


def _write_config(tmp_path: Path) -> None:
    (tmp_path / ".local81").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".local81" / "config.ini").write_text(
        CONFIG_TEMPLATE.format(
            app_source=tmp_path / "src" / "app",
            api_source=tmp_path / "src" / "api",
            disabled_source=tmp_path / "src" / "disabled",
        ),
        encoding="utf-8",
    )


def test_format_pull_command() -> None:
    command = _format_pull_command(
        host="hosta",
        target_dir=Path("/srv/app"),
        source_dir=Path("/tmp/local/app"),
        rsync_opts="-az --delete",
    )
    assert command == "rsync -az --delete -- hosta:/srv/app/ /tmp/local/app/"


def test_run_pull_dry_run_with_scope_hosts_override(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = run_pull(scope="app", hosts="hosta,hostb", dry_run=True)

    out = capsys.readouterr().out
    assert rc == 0
    assert '[pull] dry-run scope=app host=hosta cmd=rsync -az -- hosta:/srv/app/ ' in out
    assert '[pull] dry-run scope=app host=hostb cmd=rsync -az -- hostb:/srv/app/ ' in out
    assert 'Pulled files into local source dirs (success=2, failed=0)' in out


def test_run_pull_uses_subprocess_for_real_run(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    class Result:
        returncode = 0

    def fake_run(command: list[str], *, text: bool):
        calls.append(command)
        assert text is True
        return Result()

    monkeypatch.setattr("local81.commands.pull.subprocess.run", fake_run)

    rc = run_pull()

    out = capsys.readouterr().out
    assert rc == 0
    assert len(calls) == 3
    assert calls[0] == ["rsync", "-az", "--", "old1:/srv/app/", f"{tmp_path / 'src' / 'app'}/"]
    assert calls[1] == ["rsync", "-az", "--", "old2:/srv/app/", f"{tmp_path / 'src' / 'app'}/"]
    assert calls[2] == ["rsync", "-az", "--", "api1:/srv/api/", f"{tmp_path / 'src' / 'api'}/"]
    assert '[pull] scope=app host=old1 ok' in out
    assert 'Pulled files into local source dirs (success=3, failed=0)' in out


def test_run_pull_missing_scope_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = run_pull(scope="nope")

    err = capsys.readouterr().err
    assert rc == 1
    assert 'local81: no matching scopes found' in err


def test_run_pull_skips_disabled_scope(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = run_pull(scope="disabled", dry_run=True)

    out = capsys.readouterr().out
    assert rc == 0
    assert '[pull] scope=disabled skipped (disabled)' in out
    assert 'Pulled files into local source dirs (success=0, failed=0)' in out


def test_cli_pull_command() -> None:
    from local81.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["pull", "--scope", "app", "--hosts", "hosta,hostb", "--rsync-opts", "-az --delete", "--dry-run"])
    assert args.command == "pull"
    assert args.scope == "app"
    assert args.hosts == "hosta,hostb"
    assert args.rsync_opts == "-az --delete"
    assert args.dry_run is True
