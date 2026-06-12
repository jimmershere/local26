"""Deploy-time desired-state resolution.

A v2 plan step is declarative: it names an ``op`` (``file.synced``,
``dir.present``, ``service.running``, ``package.present``) plus an ``intent``,
and carries the executable ``cmd`` that converges the target. At apply time
:func:`resolve_step_action` probes the live target through a
:class:`~local81.connectors.Connector`, diffs the observed fact against the
intent via the ops layer, and reports whether the step still needs to run.

Two deliberate properties keep this safe to drop into the existing executor:

* **Opt-in.** A step with no ``op``/``intent`` returns ``(None, None)`` and the
  caller runs its ``cmd`` exactly as before — raw-command plans are untouched.
* **Fail-open.** Any probe error returns ``("unknown", …)`` so the caller still
  runs the command; the gate can only ever *skip* work it has positively proven
  is already converged, never hide a needed change behind a flaky probe.
"""

from __future__ import annotations

from typing import Any, Callable

from .connectors import Connector, LocalConnector, SshConnector
from .facts.probes import dir_state, file_state, package_state, service_state
from .ops.models import Command, DirIntent, FileIntent, PackageIntent, ServiceIntent
from .ops.operations import dir_present, file_synced, package_present, service_running

# Hosts that mean "the control node itself" — probed locally, no SSH.
_LOCAL_HOSTS = {"@local", "local"}


def connector_for_host(host: str | None, *, factory: Callable[[str | None], Connector] | None = None) -> Connector:
    if factory is not None:
        return factory(host)
    if host is None or host in _LOCAL_HOSTS:
        return LocalConnector()
    return SshConnector(host)


def resolve_step_action(
    step: dict[str, Any],
    *,
    connector: Connector | None = None,
    connector_factory: Callable[[str | None], Connector] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Decide whether a v2 op-step still needs to run.

    Returns ``(action, observed_state)`` where ``action`` is one of
    ``none``/``create``/``update``/``unknown``, or ``(None, None)`` when the
    step carries no desired-state metadata (caller runs it as-is).
    """
    op = step.get("op")
    intent = step.get("intent")
    if not op or not isinstance(intent, dict):
        return None, None

    host = step.get("host") or step.get("server")
    conn = connector or connector_for_host(host, factory=connector_factory)

    # Fail-open guard: a file.synced step with no desired content hash cannot be
    # proven converged (the diff would report 'none' for any existing target and
    # wrongly skip the push). Treat it as unknown so the caller runs the cmd.
    if op == "file.synced" and not intent.get("sha256"):
        return "unknown", {"reason": "no desired sha256 to compare"}

    try:
        if op == "file.synced":
            fact = file_state(conn, intent["path"])
            # The step's cmd is the content-placement command; pass it as the
            # intent's content_command so the diff reports create/update on
            # drift and none on a content match.
            result = file_synced(
                fact,
                FileIntent(
                    path=intent["path"],
                    sha256=intent.get("sha256"),
                    mode=intent.get("mode"),
                    owner=intent.get("owner"),
                    group=intent.get("group"),
                    content_command=Command(script=step.get("cmd") or ""),
                ),
            )
            observed = {"exists": fact.exists, "is_file": fact.is_file, "sha256": fact.sha256}
        elif op == "dir.present":
            fact = dir_state(conn, intent["path"])
            result = dir_present(
                fact,
                DirIntent(path=intent["path"], mode=intent.get("mode"), owner=intent.get("owner"), group=intent.get("group")),
            )
            observed = {"exists": fact.exists, "is_dir": fact.is_dir}
        elif op == "service.running":
            fact = service_state(conn, intent["name"])
            result = service_running(
                fact,
                ServiceIntent(name=intent["name"], active=intent.get("active", True), enabled=intent.get("enabled", True)),
            )
            observed = {"present": fact.present, "active": fact.active, "enabled": fact.enabled}
        elif op == "package.present":
            fact = package_state(conn, intent["name"])
            result = package_present(
                fact,
                PackageIntent(name=intent["name"], installed=intent.get("installed", True)),
            )
            observed = {"installed": fact.installed, "version": fact.version}
        else:
            return None, None
    except Exception as exc:  # fail-open: never hide a needed change
        return "unknown", {"error": str(exc)}

    return result.action, observed
