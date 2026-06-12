"""Typed inputs/outputs for the desired-state operations layer.

An *operation* takes a desired ``*Intent`` plus the matching read-only fact and
emits the :class:`Command` list needed to converge the target. The diff is a
pure function: given the same fact and intent it always returns the same
result, which is what makes convergence testable without a live host.

``Command`` is the atomic unit the ops layer produces. It is connector-agnostic
on purpose: a command is *what to run on the target*, and the
:class:`~local81.connectors.Connector` decides how to transport it. File
*content* placement (rsync/put) is supplied by the caller as a pre-built
``content_command`` because the transport is connector-specific and is not
formalised until Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Action verbs carried by a v2 plan step. ``none`` means the observed state
# already matches the intent and nothing will run.
ACTION_NONE = "none"
ACTION_CREATE = "create"
ACTION_UPDATE = "update"


@dataclass(slots=True, frozen=True)
class Command:
    """A single shell action to execute on the target.

    Exactly one of ``argv`` / ``script`` describes the work; ``sudo`` records
    whether the op believes elevation is required so the runner/operator can
    decide rather than the op silently escalating.
    """

    argv: list[str] | None = None
    script: str | None = None
    sudo: bool = False

    def __post_init__(self) -> None:
        if (self.argv is None) == (self.script is None):
            raise ValueError("Command requires exactly one of argv or script")


@dataclass(slots=True, frozen=True)
class OpResult:
    """Outcome of diffing one intent against one fact.

    ``action`` is the coarse verb shown to operators; ``commands`` is the
    ordered work to converge; ``reason`` explains the decision in one line so a
    plan reads honestly instead of as opaque magic.
    """

    action: str
    commands: list[Command] = field(default_factory=list)
    reason: str = ""

    @property
    def changes(self) -> bool:
        return self.action != ACTION_NONE


# --------------------------------------------------------------------------- #
# desired-state intents
# --------------------------------------------------------------------------- #
@dataclass(slots=True, frozen=True)
class FileIntent:
    """Desired state of a file on the target.

    ``sha256`` is the desired content hash (computed by the caller from the
    source); when it differs from the observed hash the op runs
    ``content_command`` to (re)place the bytes. Metadata fields are only
    enforced when set, so a partial intent never clobbers attributes the
    operator did not ask to manage.
    """

    path: str
    sha256: str | None = None
    mode: str | None = None
    owner: str | None = None
    group: str | None = None
    content_command: Command | None = None


@dataclass(slots=True, frozen=True)
class DirIntent:
    path: str
    mode: str | None = None
    owner: str | None = None
    group: str | None = None


@dataclass(slots=True, frozen=True)
class ServiceIntent:
    name: str
    active: bool = True
    enabled: bool = True


@dataclass(slots=True, frozen=True)
class PackageIntent:
    name: str
    installed: bool = True
    # Caller supplies the install/remove command because the package manager
    # and any flags are environment-specific; the op only decides *whether* it
    # must run based on the observed PackageState.
    install_command: Command | None = None
    remove_command: Command | None = None


@dataclass(slots=True, frozen=True)
class CommandIntent:
    """A raw command guarded for idempotency.

    The command runs only when the guard is unsatisfied:

    * ``creates`` — a path; skip if it already exists.
    * ``unless_ok`` — a CommandProbe was already run; skip if it succeeded.

    With no guard the op is honestly labelled non-idempotent: it runs every
    time, and ``diff`` says so.
    """

    command: Command
    creates: str | None = None
    unless_ok: bool | None = None
