from __future__ import annotations

from local81.facts.models import DirState, FileState, PackageState, ServiceState
from local81.ops import (
    ACTION_CREATE,
    ACTION_NONE,
    ACTION_UPDATE,
    Command,
    CommandIntent,
    DirIntent,
    FileIntent,
    PackageIntent,
    ServiceIntent,
    command_run,
    command_run_idempotent,
    dir_present,
    file_synced,
    package_present,
    service_running,
)


# --------------------------------------------------------------------------- #
# Command invariants
# --------------------------------------------------------------------------- #
def test_command_requires_exactly_one_payload():
    Command(argv=["ls"])
    Command(script="ls")
    for bad in (lambda: Command(), lambda: Command(argv=["ls"], script="ls")):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("expected ValueError for ambiguous Command payload")


# --------------------------------------------------------------------------- #
# file.synced
# --------------------------------------------------------------------------- #
def _push(path: str) -> Command:
    return Command(argv=["rsync", "--", "local", path])


def test_file_synced_creates_when_absent():
    fact = FileState(path="/srv/app.ini", exists=False)
    intent = FileIntent(path="/srv/app.ini", sha256="abc", content_command=_push("/srv/app.ini"))
    res = file_synced(fact, intent)
    assert res.action == ACTION_CREATE
    assert res.commands == [_push("/srv/app.ini")]


def test_file_synced_updates_on_content_drift():
    fact = FileState(path="/srv/app.ini", exists=True, is_file=True, sha256="old")
    intent = FileIntent(path="/srv/app.ini", sha256="new", content_command=_push("/srv/app.ini"))
    res = file_synced(fact, intent)
    assert res.action == ACTION_UPDATE
    assert res.commands == [_push("/srv/app.ini")]
    assert "content differs" in res.reason


def test_file_synced_noop_when_matching():
    fact = FileState(path="/srv/app.ini", exists=True, is_file=True, sha256="same", mode="644", owner="deploy", group="deploy")
    intent = FileIntent(path="/srv/app.ini", sha256="same", mode="644", owner="deploy", group="deploy")
    res = file_synced(fact, intent)
    assert res.action == ACTION_NONE
    assert res.commands == []
    assert res.changes is False


def test_file_synced_fixes_mode_only():
    fact = FileState(path="/srv/app.ini", exists=True, is_file=True, sha256="same", mode="600")
    intent = FileIntent(path="/srv/app.ini", sha256="same", mode="644")
    res = file_synced(fact, intent)
    assert res.action == ACTION_UPDATE
    assert res.commands == [Command(argv=["chmod", "644", "--", "/srv/app.ini"])]


def test_file_synced_chown_is_sudo_and_combines_owner_group():
    fact = FileState(path="/srv/app.ini", exists=True, is_file=True, sha256="same", owner="root", group="root")
    intent = FileIntent(path="/srv/app.ini", sha256="same", owner="deploy", group="web")
    res = file_synced(fact, intent)
    assert res.commands == [Command(argv=["chown", "deploy:web", "--", "/srv/app.ini"], sudo=True)]


def test_file_synced_unmanaged_metadata_is_left_alone():
    # owner/group unset on intent -> never emit chown even if they differ.
    fact = FileState(path="/srv/app.ini", exists=True, is_file=True, sha256="same", owner="root", mode="644")
    intent = FileIntent(path="/srv/app.ini", sha256="same", mode="644")
    res = file_synced(fact, intent)
    assert res.action == ACTION_NONE


# --------------------------------------------------------------------------- #
# dir.present
# --------------------------------------------------------------------------- #
def test_dir_present_creates_when_absent():
    res = dir_present(DirState(path="/srv/x", exists=False), DirIntent(path="/srv/x", mode="750"))
    assert res.action == ACTION_CREATE
    assert res.commands[0] == Command(argv=["mkdir", "-p", "--", "/srv/x"])
    assert Command(argv=["chmod", "750", "--", "/srv/x"]) in res.commands


def test_dir_present_noop_when_matching():
    fact = DirState(path="/srv/x", exists=True, is_dir=True, mode="750", owner="deploy", group="web")
    intent = DirIntent(path="/srv/x", mode="750", owner="deploy", group="web")
    assert dir_present(fact, intent).action == ACTION_NONE


def test_dir_present_path_is_file_is_treated_as_absent():
    fact = DirState(path="/srv/x", exists=True, is_dir=False)
    res = dir_present(fact, DirIntent(path="/srv/x"))
    assert res.action == ACTION_CREATE


# --------------------------------------------------------------------------- #
# service.running
# --------------------------------------------------------------------------- #
def test_service_running_starts_and_enables():
    fact = ServiceState(name="nginx", present=True, active=False, enabled=False)
    res = service_running(fact, ServiceIntent(name="nginx"))
    assert res.action == ACTION_UPDATE
    assert Command(argv=["systemctl", "start", "--", "nginx"], sudo=True) in res.commands
    assert Command(argv=["systemctl", "enable", "--", "nginx"], sudo=True) in res.commands


def test_service_running_noop_when_active_enabled():
    fact = ServiceState(name="nginx", present=True, active=True, enabled=True)
    assert service_running(fact, ServiceIntent(name="nginx")).action == ACTION_NONE


def test_service_running_absent_unit_is_create():
    fact = ServiceState(name="ghost", present=False, active=False, enabled=False)
    res = service_running(fact, ServiceIntent(name="ghost"))
    assert res.action == ACTION_CREATE


def test_service_running_can_stop_and_disable():
    fact = ServiceState(name="nginx", present=True, active=True, enabled=True)
    res = service_running(fact, ServiceIntent(name="nginx", active=False, enabled=False))
    assert Command(argv=["systemctl", "stop", "--", "nginx"], sudo=True) in res.commands
    assert Command(argv=["systemctl", "disable", "--", "nginx"], sudo=True) in res.commands


# --------------------------------------------------------------------------- #
# package.present
# --------------------------------------------------------------------------- #
def test_package_present_installs_when_missing():
    fact = PackageState(name="rsync", installed=False)
    intent = PackageIntent(name="rsync", install_command=Command(argv=["apt-get", "install", "-y", "rsync"], sudo=True))
    res = package_present(fact, intent)
    assert res.action == ACTION_CREATE
    assert res.commands[0].sudo is True


def test_package_present_noop_when_installed():
    fact = PackageState(name="rsync", installed=True, version="3.2.7-1")
    assert package_present(fact, PackageIntent(name="rsync")).action == ACTION_NONE


def test_package_present_absent_without_command_is_honest_noop_commands():
    fact = PackageState(name="rsync", installed=False)
    res = package_present(fact, PackageIntent(name="rsync"))
    assert res.action == ACTION_CREATE
    assert res.commands == []
    assert "no install_command" in res.reason


# --------------------------------------------------------------------------- #
# command.run (guarded idempotency)
# --------------------------------------------------------------------------- #
def test_command_run_unguarded_is_not_idempotent():
    intent = CommandIntent(command=Command(argv=["./migrate.sh"]))
    assert command_run_idempotent(intent) is False
    res = command_run(intent)
    assert res.action == ACTION_CREATE
    assert "no guard" in res.reason


def test_command_run_creates_guard_skips_when_path_exists():
    intent = CommandIntent(command=Command(argv=["tar", "xf", "app.tgz"]), creates="/srv/app")
    assert command_run_idempotent(intent) is True
    assert command_run(intent, creates_exists=True).action == ACTION_NONE
    assert command_run(intent, creates_exists=False).action == ACTION_CREATE


def test_command_run_unless_guard_skips_when_satisfied():
    intent = CommandIntent(command=Command(argv=["init-db"]), unless_ok=True)
    assert command_run(intent).action == ACTION_NONE


# --------------------------------------------------------------------------- #
# convergence: applying a converged plan again is a full no-op
# --------------------------------------------------------------------------- #
def test_convergence_second_pass_is_all_none():
    # First pass: everything drifted; second pass: facts now match intent.
    drifted = [
        file_synced(FileState(path="/a", exists=False), FileIntent(path="/a", sha256="h", content_command=_push("/a"))),
        dir_present(DirState(path="/d", exists=False), DirIntent(path="/d")),
        service_running(ServiceState(name="s", present=True), ServiceIntent(name="s")),
        package_present(PackageState(name="p", installed=False), PackageIntent(name="p", install_command=Command(argv=["i"]))),
    ]
    assert all(r.changes for r in drifted)

    converged = [
        file_synced(FileState(path="/a", exists=True, is_file=True, sha256="h"), FileIntent(path="/a", sha256="h", content_command=_push("/a"))),
        dir_present(DirState(path="/d", exists=True, is_dir=True), DirIntent(path="/d")),
        service_running(ServiceState(name="s", present=True, active=True, enabled=True), ServiceIntent(name="s")),
        package_present(PackageState(name="p", installed=True), PackageIntent(name="p", install_command=Command(argv=["i"]))),
    ]
    assert all(r.action == ACTION_NONE for r in converged)
    assert all(not r.commands for r in converged)
