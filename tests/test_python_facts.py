from __future__ import annotations

from local81.connectors import LocalConnector
from local81.facts import (
    command_probe,
    dir_state,
    file_state,
    package_state,
    parse_dir_state,
    parse_file_state,
    parse_package_state,
    parse_service_state,
    service_state,
)
from local81.facts.probes import service_state_probe
from local81.models import CommandResult


class MockConnector:
    """Connector that returns canned stdout regardless of the command."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.name = "@mock"
        self._stdout = stdout
        self._returncode = returncode
        self._stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, command, *, timeout_seconds=None, env=None) -> CommandResult:
        argv = command if isinstance(command, list) else ["sh", "-c", command]
        self.calls.append(argv)
        return CommandResult(
            command=argv,
            returncode=self._returncode,
            stdout=self._stdout,
            stderr=self._stderr,
        )


# --------------------------------------------------------------------------- #
# parser golden tests
# --------------------------------------------------------------------------- #
def test_parse_file_state_present():
    stdout = "exists=1\nis_file=1\nmeta=644|deploy|deploy|2048\nsha256=abc123\n"
    fs = parse_file_state("/srv/app/config.ini", stdout)
    assert fs.exists is True
    assert fs.is_file is True
    assert fs.mode == "644"
    assert fs.owner == "deploy"
    assert fs.group == "deploy"
    assert fs.size == 2048
    assert fs.sha256 == "abc123"


def test_parse_file_state_absent():
    fs = parse_file_state("/nope", "exists=0\n")
    assert fs.exists is False
    assert fs.is_file is False
    assert fs.sha256 is None


def test_parse_file_state_directory_has_no_sha():
    stdout = "exists=1\nis_file=0\nmeta=755|root|root|4096\n"
    fs = parse_file_state("/srv/app", stdout)
    assert fs.exists is True
    assert fs.is_file is False
    assert fs.sha256 is None
    assert fs.mode == "755"


def test_parse_dir_state_present():
    ds = parse_dir_state("/srv/app", "exists=1\nis_dir=1\nmeta=750|deploy|web\n")
    assert ds.exists is True
    assert ds.is_dir is True
    assert ds.mode == "750"
    assert ds.owner == "deploy"
    assert ds.group == "web"


def test_parse_dir_state_path_is_file():
    ds = parse_dir_state("/srv/app/file", "exists=1\nis_dir=0\nmeta=644|deploy|deploy\n")
    assert ds.exists is True
    assert ds.is_dir is False


def test_parse_dir_state_absent():
    ds = parse_dir_state("/missing", "exists=0\nis_dir=0\n")
    assert ds.exists is False
    assert ds.is_dir is False


def test_parse_service_state_active_enabled():
    ss = parse_service_state("nginx", "active=active\nenabled=enabled\n")
    assert ss.present is True
    assert ss.active is True
    assert ss.enabled is True


def test_parse_service_state_inactive_disabled():
    ss = parse_service_state("nginx", "active=inactive\nenabled=disabled\n")
    assert ss.present is True
    assert ss.active is False
    assert ss.enabled is False


def test_parse_service_state_absent_unit():
    ss = parse_service_state("ghost", "active=\nenabled=\n")
    assert ss.present is False
    assert ss.active is False


def test_parse_package_state_dpkg_installed():
    ps = parse_package_state("rsync", "manager=dpkg\nresult=install ok installed|3.2.7-1\n")
    assert ps.installed is True
    assert ps.version == "3.2.7-1"
    assert ps.manager == "dpkg"


def test_parse_package_state_dpkg_missing():
    ps = parse_package_state("ghostpkg", "manager=dpkg\nresult=\n")
    assert ps.installed is False
    assert ps.version is None


def test_parse_package_state_rpm_installed():
    ps = parse_package_state("httpd", "manager=rpm\nresult=2.4.57-5.el9\n")
    assert ps.installed is True
    assert ps.version == "2.4.57-5.el9"
    assert ps.manager == "rpm"


def test_parse_package_state_no_manager():
    ps = parse_package_state("rsync", "manager=none\n")
    assert ps.installed is False
    assert ps.manager == "none"


# --------------------------------------------------------------------------- #
# fact functions via mock connector
# --------------------------------------------------------------------------- #
def test_file_state_uses_connector():
    conn = MockConnector(stdout="exists=1\nis_file=1\nmeta=600|deploy|deploy|10\nsha256=deadbeef\n")
    fs = file_state(conn, "/srv/secret")
    assert fs.sha256 == "deadbeef"
    assert fs.mode == "600"
    assert conn.calls, "connector should have been invoked"


def test_dir_state_uses_connector():
    conn = MockConnector(stdout="exists=1\nis_dir=1\nmeta=700|root|root\n")
    ds = dir_state(conn, "/srv")
    assert ds.is_dir is True


def test_service_state_uses_connector():
    conn = MockConnector(stdout="active=active\nenabled=enabled\n")
    ss = service_state(conn, "nginx")
    assert ss.active and ss.enabled


def test_package_state_uses_connector():
    conn = MockConnector(stdout="manager=dpkg\nresult=install ok installed|1.0\n")
    ps = package_state(conn, "demo")
    assert ps.installed is True


def test_command_probe_reports_returncode():
    conn = MockConnector(stdout="hello\n", returncode=3, stderr="boom")
    probe = command_probe(conn, ["test", "-f", "/x"])
    assert probe.returncode == 3
    assert probe.ok is False
    assert probe.stdout == "hello\n"


def test_probe_escapes_paths_against_injection():
    # A malicious path must end up quoted inside the script, not interpolated raw.
    probe = service_state_probe("nginx; rm -rf /")
    script = probe[-1]
    assert "'nginx; rm -rf /'" in script


# --------------------------------------------------------------------------- #
# integration: real LocalConnector against the filesystem (no SSH needed)
# --------------------------------------------------------------------------- #
def test_file_state_local_roundtrip(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("hi\n", encoding="utf-8")
    fs = file_state(LocalConnector(), str(target))
    assert fs.exists is True
    assert fs.is_file is True
    assert fs.sha256 and len(fs.sha256) == 64


def test_file_state_local_absent(tmp_path):
    fs = file_state(LocalConnector(), str(tmp_path / "nope"))
    assert fs.exists is False


def test_dir_state_local_roundtrip(tmp_path):
    ds = dir_state(LocalConnector(), str(tmp_path))
    assert ds.exists is True
    assert ds.is_dir is True
