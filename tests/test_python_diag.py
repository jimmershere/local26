from __future__ import annotations

import csv
from pathlib import Path

from seraf.commands.diag import diag_remote_command_for_type, resolve_diag_hosts_for_project, run_diag


def test_diag_remote_command_for_type_variants() -> None:
    assert diag_remote_command_for_type("strace", "4242", "20s") == "timeout 20s strace -f -tt -s 256 -p 4242"
    assert diag_remote_command_for_type("py-spy", "4242", "10s") == "timeout 10s py-spy dump --pid 4242 --native --locals"
    assert diag_remote_command_for_type("austin", "4242", "5s") == "timeout 5s austin -Cp 4242"


def test_resolve_diag_hosts_for_project_aliases() -> None:
    hosts = resolve_diag_hosts_for_project("m2-project", "cmsap1,cmspr1")
    assert hosts == "10.242.225.11,10.242.209.11"


def test_resolve_diag_hosts_for_project_rejects_disabled_host() -> None:
    try:
        resolve_diag_hosts_for_project("m2-project", "cmppr1")
    except ValueError as exc:
        assert "unknown or disabled host token" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_run_diag_dry_run_writes_manifest(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "diag"

    rc = run_diag(hosts="127.0.0.1", remote_cmd="uname -a", out_dir=str(out_dir), dry_run=True)

    out = capsys.readouterr().out
    assert rc == 0
    assert "[diag] host=127.0.0.1 rc=0" in out
    assert "[diag] manifest=" in out
    assert (out_dir / "127.0.0.1.stdout.log").read_text(encoding="utf-8") == "dry-run ssh 127.0.0.1 uname -a\n"

    with (out_dir / "diag-run.tsv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert rows == [{
        "host": "127.0.0.1",
        "rc": "0",
        "stdout": str(out_dir / "127.0.0.1.stdout.log"),
        "stderr": str(out_dir / "127.0.0.1.stderr.log"),
        "cmd": "uname -a",
    }]


def test_run_diag_invokes_ssh(tmp_path: Path, monkeypatch, capsys) -> None:
    out_dir = tmp_path / "diag"
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "stdout:cmsap1\n"
        stderr = "stderr:cmsap1\n"

    def fake_run(command: list[str], *, capture_output: bool, text: bool):
        calls.append(command)
        assert capture_output is True
        assert text is True
        return Result()

    monkeypatch.setattr("seraf.commands.diag.subprocess.run", fake_run)

    rc = run_diag(project="m2-project", hosts="cmsap1", pid="4242", out_dir=str(out_dir))

    out = capsys.readouterr().out
    assert rc == 0
    assert calls == [["ssh", "10.242.225.11", "timeout 20s strace -f -tt -s 256 -p 4242"]]
    assert (out_dir / "10.242.225.11.stdout.log").read_text(encoding="utf-8") == "stdout:cmsap1\n"
    assert "[diag] host=10.242.225.11 rc=0" in out


def test_run_diag_requires_pid_without_remote_cmd(capsys) -> None:
    rc = run_diag(hosts="127.0.0.1")
    out = capsys.readouterr().out
    assert rc == 2
    assert "--pid is required unless --remote-cmd is provided" in out


def test_cli_diag_command() -> None:
    from seraf.cli import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "diag",
        "--project", "m2-project",
        "--hosts", "cmsap1,cmspr1",
        "--diag-type", "strace",
        "--pid", "4242",
        "--duration", "30s",
        "--out-dir", "/tmp/diag",
        "--ssh-user", "deploy",
        "--include-disabled",
        "--dry-run",
    ])
    assert args.command == "diag"
    assert args.project == "m2-project"
    assert args.hosts == "cmsap1,cmspr1"
    assert args.diag_type == "strace"
    assert args.pid == "4242"
    assert args.duration == "30s"
    assert args.out_dir == "/tmp/diag"
    assert args.ssh_user == "deploy"
    assert args.include_disabled is True
    assert args.dry_run is True
