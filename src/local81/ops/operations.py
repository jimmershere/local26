"""Desired-state operations: pure ``diff(fact, intent) -> OpResult`` functions.

Each operation mirrors a fact from :mod:`local81.facts`. The diff is the whole
point of the idempotency layer: it compares observed state against intent and
emits only the commands needed to converge. Running a plan twice should yield
``action=none`` everywhere on the second pass, because the facts now match.

Every op also declares ``idempotent`` honestly. ``command.run`` is the one that
can be non-idempotent (no guard), and it admits that rather than pretending.
"""

from __future__ import annotations

from ..facts.models import DirState, FileState, PackageState, ServiceState
from .models import (
    ACTION_CREATE,
    ACTION_NONE,
    ACTION_UPDATE,
    Command,
    CommandIntent,
    DirIntent,
    FileIntent,
    OpResult,
    PackageIntent,
    ServiceIntent,
)


def _meta_commands(path: str, fact_mode, fact_owner, fact_group, intent) -> list[Command]:
    """Emit chmod/chown for metadata that is set on the intent and drifted."""
    cmds: list[Command] = []
    if intent.mode is not None and fact_mode != intent.mode:
        cmds.append(Command(argv=["chmod", intent.mode, "--", path]))
    # Ownership: a single chown handles owner and/or group. Ownership changes
    # require root, so mark sudo honestly rather than failing at apply time.
    owner_drift = intent.owner is not None and fact_owner != intent.owner
    group_drift = intent.group is not None and fact_group != intent.group
    if owner_drift or group_drift:
        spec = (intent.owner or "") + (f":{intent.group}" if group_drift else "")
        cmds.append(Command(argv=["chown", spec, "--", path], sudo=True))
    return cmds


# --------------------------------------------------------------------------- #
# file.synced
# --------------------------------------------------------------------------- #
file_synced_idempotent = True


def file_synced(fact: FileState, intent: FileIntent) -> OpResult:
    not_present = not fact.exists or not fact.is_file
    content_drift = intent.sha256 is not None and fact.sha256 != intent.sha256

    commands: list[Command] = []
    if (not_present or content_drift) and intent.content_command is not None:
        commands.append(intent.content_command)

    commands.extend(_meta_commands(intent.path, fact.mode, fact.owner, fact.group, intent))

    if not commands:
        return OpResult(ACTION_NONE, [], f"{intent.path} already matches intent")
    if not_present:
        return OpResult(ACTION_CREATE, commands, f"{intent.path} is absent")
    reason = "content differs" if content_drift else "metadata differs"
    return OpResult(ACTION_UPDATE, commands, f"{intent.path}: {reason}")


# --------------------------------------------------------------------------- #
# dir.present
# --------------------------------------------------------------------------- #
dir_present_idempotent = True


def dir_present(fact: DirState, intent: DirIntent) -> OpResult:
    commands: list[Command] = []
    not_present = not fact.exists or not fact.is_dir
    if not_present:
        commands.append(Command(argv=["mkdir", "-p", "--", intent.path]))

    commands.extend(_meta_commands(intent.path, fact.mode, fact.owner, fact.group, intent))

    if not commands:
        return OpResult(ACTION_NONE, [], f"{intent.path} already present")
    if not_present:
        return OpResult(ACTION_CREATE, commands, f"{intent.path} is absent")
    return OpResult(ACTION_UPDATE, commands, f"{intent.path}: metadata differs")


# --------------------------------------------------------------------------- #
# service.running
# --------------------------------------------------------------------------- #
service_running_idempotent = True


def service_running(fact: ServiceState, intent: ServiceIntent) -> OpResult:
    commands: list[Command] = []
    if intent.active and not fact.active:
        commands.append(Command(argv=["systemctl", "start", "--", fact.name], sudo=True))
    elif not intent.active and fact.active:
        commands.append(Command(argv=["systemctl", "stop", "--", fact.name], sudo=True))

    if intent.enabled and not fact.enabled:
        commands.append(Command(argv=["systemctl", "enable", "--", fact.name], sudo=True))
    elif not intent.enabled and fact.enabled:
        commands.append(Command(argv=["systemctl", "disable", "--", fact.name], sudo=True))

    if not commands:
        return OpResult(ACTION_NONE, [], f"{fact.name} already in desired state")
    # A unit that isn't present yet can't be started; the diff still surfaces
    # the intent so the operator sees the gap instead of a silent no-op.
    action = ACTION_CREATE if not fact.present else ACTION_UPDATE
    return OpResult(action, commands, f"{fact.name}: service state differs")


# --------------------------------------------------------------------------- #
# package.present
# --------------------------------------------------------------------------- #
package_present_idempotent = True


def package_present(fact: PackageState, intent: PackageIntent) -> OpResult:
    if intent.installed and not fact.installed:
        if intent.install_command is None:
            return OpResult(ACTION_CREATE, [], f"{fact.name} absent but no install_command supplied")
        return OpResult(ACTION_CREATE, [intent.install_command], f"{fact.name} is not installed")
    if not intent.installed and fact.installed:
        if intent.remove_command is None:
            return OpResult(ACTION_UPDATE, [], f"{fact.name} present but no remove_command supplied")
        return OpResult(ACTION_UPDATE, [intent.remove_command], f"{fact.name} is installed")
    return OpResult(ACTION_NONE, [], f"{fact.name} already in desired state")


# --------------------------------------------------------------------------- #
# command.run
# --------------------------------------------------------------------------- #
def command_run_idempotent(intent: CommandIntent) -> bool:
    """A raw command is only idempotent when a guard lets it be skipped."""
    return intent.creates is not None or intent.unless_ok is not None


def command_run(intent: CommandIntent, *, creates_exists: bool = False) -> OpResult:
    """Decide whether a guarded command must run.

    ``creates_exists`` reports whether the ``creates`` path was observed on the
    target (the caller probes it). ``unless_ok`` carries the result of a
    pre-run CommandProbe. With neither guard the command always runs and the
    reason says so plainly.
    """
    if intent.creates is not None and creates_exists:
        return OpResult(ACTION_NONE, [], f"creates path exists: {intent.creates}")
    if intent.unless_ok is True:
        return OpResult(ACTION_NONE, [], "unless guard already satisfied")
    reason = "guard unsatisfied" if command_run_idempotent(intent) else "no guard (runs every apply)"
    return OpResult(ACTION_CREATE, [intent.command], reason)
