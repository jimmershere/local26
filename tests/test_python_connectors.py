from __future__ import annotations

from pathlib import Path

import local81.connectors as connectors
from local81.connectors import (
    Connector,
    DockerConnector,
    LocalConnector,
    SshConnector,
    connector_for_target,
)
from local81.models import CommandResult
from local81.resolve import connector_for_host


def test_connector_for_target_routes_by_prefix() -> None:
    assert isinstance(connector_for_target(None), LocalConnector)
    assert isinstance(connector_for_target("@local"), LocalConnector)
    assert isinstance(connector_for_target("local"), LocalConnector)

    docker = connector_for_target("@docker/web")
    assert isinstance(docker, DockerConnector)
    assert docker.container == "web"
    assert docker.name == "@docker/web"

    ssh = connector_for_target("db01.example.com")
    assert isinstance(ssh, SshConnector)
    assert ssh.name == "db01.example.com"


def test_resolve_routes_docker_target_to_docker_connector() -> None:
    # The probe gate must honour @docker/<name> targets, not treat them as SSH.
    conn = connector_for_host("@docker/api")
    assert isinstance(conn, DockerConnector)
    assert conn.container == "api"


def test_local_connector_put_and_get_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload", encoding="utf-8")
    dest = tmp_path / "nested" / "dest.txt"

    conn = LocalConnector()
    put = conn.put(str(src), str(dest))
    assert put.returncode == 0
    assert dest.read_text(encoding="utf-8") == "payload"

    back = tmp_path / "back.txt"
    got = conn.get(str(dest), str(back))
    assert got.returncode == 0
    assert back.read_text(encoding="utf-8") == "payload"


def test_local_connector_put_directory_recursive(tmp_path: Path) -> None:
    src_dir = tmp_path / "tree"
    (src_dir / "a").mkdir(parents=True)
    (src_dir / "a" / "f.txt").write_text("x", encoding="utf-8")
    dest_dir = tmp_path / "copied"

    conn = LocalConnector()
    result = conn.put(str(src_dir), str(dest_dir), recursive=True)
    assert result.returncode == 0
    assert (dest_dir / "a" / "f.txt").read_text(encoding="utf-8") == "x"


def test_local_connector_put_missing_source_fails(tmp_path: Path) -> None:
    conn = LocalConnector()
    result = conn.put(str(tmp_path / "nope.txt"), str(tmp_path / "out.txt"))
    assert result.returncode == 1
    assert "local put failed" in result.stderr


def test_ssh_connector_put_builds_rsync_argv(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run_local(argv, **_kwargs):
        captured["argv"] = argv
        return CommandResult(command=argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(connectors, "run_local", fake_run_local)

    conn = SshConnector("host1", rsync_opts="-az --delete")
    conn.put("/local/f", "/remote/f")

    assert captured["argv"] == ["rsync", "-az", "--delete", "--", "/local/f", "host1:/remote/f"]


def test_ssh_connector_get_builds_rsync_argv(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run_local(argv, **_kwargs):
        captured["argv"] = argv
        return CommandResult(command=argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(connectors, "run_local", fake_run_local)

    conn = SshConnector("host1")
    conn.get("/remote/f", "/local/f")

    assert captured["argv"] == ["rsync", "-az", "--", "host1:/remote/f", "/local/f"]


def test_docker_connector_run_builds_exec_argv(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run_local(argv, **_kwargs):
        captured["argv"] = argv
        return CommandResult(command=argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(connectors, "run_local", fake_run_local)

    conn = DockerConnector("web")
    conn.run("echo hi", env={"K": "v"})

    assert captured["argv"] == ["docker", "exec", "--env", "K=v", "web", "sh", "-c", "echo hi"]


def test_docker_connector_cp_argv(monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_run_local(argv, **_kwargs):
        captured.append(argv)
        return CommandResult(command=argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(connectors, "run_local", fake_run_local)

    conn = DockerConnector("web")
    conn.put("/local/f", "/remote/f")
    conn.get("/remote/f", "/local/f")

    assert captured[0] == ["docker", "cp", "/local/f", "web:/remote/f"]
    assert captured[1] == ["docker", "cp", "web:/remote/f", "/local/f"]


class EchoConnector:
    """A toy connector proving the protocol is implementable in-tree-free.

    It touches no facts/ops code — it only satisfies the run/put/get/close
    surface. If this stops type-checking or running, the Connector contract has
    grown a hidden dependency and the extensibility guarantee is broken.
    """

    def __init__(self, name: str = "@echo") -> None:
        self.name = name
        self.calls: list[str] = []

    def run(self, command, *, timeout_seconds=None, env=None) -> CommandResult:
        script = command if isinstance(command, str) else " ".join(command)
        self.calls.append(script)
        return CommandResult(command=[script], returncode=0, stdout=script, stderr="")

    def put(self, local_path, remote_path, *, recursive=False) -> CommandResult:
        return CommandResult(command=["put", local_path, remote_path], returncode=0, stdout="", stderr="")

    def get(self, remote_path, local_path, *, recursive=False) -> CommandResult:
        return CommandResult(command=["get", remote_path, local_path], returncode=0, stdout="", stderr="")

    def close(self) -> None:
        return None


def test_echo_connector_satisfies_protocol() -> None:
    conn = EchoConnector()
    assert isinstance(conn, Connector)

    result = conn.run("uptime")
    assert result.returncode == 0
    assert result.stdout == "uptime"
    assert conn.calls == ["uptime"]


def test_echo_connector_drives_resolve_without_real_target() -> None:
    # A step probed through a custom connector resolves like any built-in one,
    # confirming resolve depends only on the Connector surface.
    from local81.resolve import resolve_step_action

    conn = EchoConnector()
    step = {
        "op": "dir.present",
        "intent": {"path": "/srv/app"},
        "host": "@echo",
        "cmd": "mkdir -p /srv/app",
    }
    # EchoConnector.run returns rc 0 with the script echoed; dir_state will read
    # that as the probe output. We only assert resolve runs end-to-end via the
    # injected connector and yields a known action label.
    action, observed = resolve_step_action(step, connector=conn)
    assert action in {"none", "create", "unknown"}
    assert observed is not None
