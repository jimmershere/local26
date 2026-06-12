"""Connector abstraction: a uniform way for facts and ops to execute commands.

Phase 2 only needs read-only command execution, so the protocol here is
intentionally minimal: a single ``run`` method returning a ``CommandResult``.
Phase 3 (Gap 6) formalises the full connector index and will extend this
protocol with file transfer (``put``/``get``) and lifecycle (``close``)
methods plus SSH/Docker implementations. Keeping the surface small now means
facts and ops only ever depend on ``Connector.run``.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from .models import CommandResult
from .runner import run_local, run_remote


@runtime_checkable
class Connector(Protocol):
    """Executes a command against a target and returns its result.

    Implementations must not mutate target state as a side effect of ``run``
    itself; idempotency and change decisions live in the ops layer. Facts use
    ``run`` exclusively for read-only probes.
    """

    name: str

    def run(
        self,
        command: str | list[str],
        *,
        timeout_seconds: int | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...


class LocalConnector:
    """Runs commands on the control node itself (``@local`` target).

    Makes localhost a first-class target so the fact/op layers are testable
    without any SSH fixtures.
    """

    def __init__(self, name: str = "@local") -> None:
        self.name = name

    def run(
        self,
        command: str | list[str],
        *,
        timeout_seconds: int | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        return run_local(command, timeout_seconds=timeout_seconds, env=env)


class SshConnector:
    """Runs commands on a remote host over SSH.

    Thin wrapper over the existing ``run_remote`` path so facts can probe
    remote targets today. Phase 3 will absorb the full rsync ``put``/``get``
    surface; for now this provides read-only ``run`` only.
    """

    def __init__(self, host: str, *, ssh_bin: str = "ssh") -> None:
        self.name = host
        self._host = host
        self._ssh_bin = ssh_bin

    def run(
        self,
        command: str | list[str],
        *,
        timeout_seconds: int | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        if isinstance(command, list):
            import shlex

            remote = " ".join(shlex.quote(part) for part in command)
        else:
            remote = command
        return run_remote(
            self._host,
            remote,
            ssh_bin=self._ssh_bin,
            timeout_seconds=timeout_seconds,
        )
