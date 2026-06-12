"""Scheduling & triggers: render operator-installable systemd timers.

Local-81 is push-based and never runs a daemon, so it does not *install* or
*own* a scheduler. Instead ``schedule add`` renders a plain
``.service`` + ``.timer`` pair (plus a ``flock`` wrapper) into
``.local81/schedules/`` for the operator to copy into ``/etc/systemd/system``.
This keeps the honesty guarantee: every artifact is human-greppable, the
operator stays in control of the live system, and nothing is hidden behind a
magic background process.

Two safety properties are baked into the rendered units:

* **No overlap.** The wrapper runs the command under ``flock -n`` against a
  per-schedule lock, so a slow run never stacks on the next timer fire — the
  later fire exits immediately rather than running concurrently.
* **Visible notification.** An optional ``notify_url`` becomes a best-effort
  ``ExecStartPost`` ``curl`` so a downstream system (e.g. n8n) learns the run
  finished, without Local-81 itself holding a long-lived connection.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .paths import Local81Paths, build_paths

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
# OnCalendar is validated loosely: systemd owns the real grammar. We only reject
# empty values and shell metacharacters that have no place in a calendar spec.
_CALENDAR_FORBIDDEN = set(";&|`$<>\n\r")


class ScheduleError(ValueError):
    """Raised for malformed schedule definitions or names."""


@dataclass(frozen=True, slots=True)
class ScheduleDef:
    name: str
    command: list[str]
    on_calendar: str
    notify_url: str | None = None
    description: str | None = None
    working_dir: str | None = None

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "command": list(self.command),
            "on_calendar": self.on_calendar,
        }
        if self.notify_url:
            data["notify_url"] = self.notify_url
        if self.description:
            data["description"] = self.description
        if self.working_dir:
            data["working_dir"] = self.working_dir
        return data

    @classmethod
    def from_dict(cls, data: dict) -> ScheduleDef:
        try:
            name = str(data["name"])
            command = list(data["command"])
            on_calendar = str(data["on_calendar"])
        except (KeyError, TypeError) as exc:
            raise ScheduleError(f"schedule definition missing required field: {exc}") from exc
        if not command or not all(isinstance(part, str) for part in command):
            raise ScheduleError(f"schedule {name!r} command must be a non-empty list of strings")
        return cls(
            name=name,
            command=command,
            on_calendar=on_calendar,
            notify_url=data.get("notify_url"),
            description=data.get("description"),
            working_dir=data.get("working_dir"),
        )


def validate_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ScheduleError(
            f"schedule name {name!r} must be lowercase alnum/_/- and start alphanumeric"
        )
    return name


def validate_calendar(spec: str) -> str:
    if not spec or not spec.strip():
        raise ScheduleError("OnCalendar value must not be empty")
    if _CALENDAR_FORBIDDEN & set(spec):
        raise ScheduleError(f"OnCalendar value {spec!r} contains illegal characters")
    return spec


def validate_notify_url(url: str | None) -> str | None:
    if url is None:
        return None
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ScheduleError(f"notify_url {url!r} must be an http(s) URL")
    return url


def validate(defn: ScheduleDef) -> ScheduleDef:
    validate_name(defn.name)
    validate_calendar(defn.on_calendar)
    validate_notify_url(defn.notify_url)
    if not defn.command:
        raise ScheduleError(f"schedule {defn.name!r} has an empty command")
    return defn


# --- store -----------------------------------------------------------------


@dataclass(slots=True)
class ScheduleStore:
    paths: Local81Paths = field(default_factory=build_paths)

    @property
    def root(self) -> Path:
        return self.paths.schedules_dir

    @property
    def units_dir(self) -> Path:
        return self.root / "systemd"

    def def_path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def lock_path(self, name: str) -> Path:
        return self.root / f"{name}.lock"

    def wrapper_path(self, name: str) -> Path:
        return self.units_dir / f"local81-{name}.sh"

    def service_path(self, name: str) -> Path:
        return self.units_dir / f"local81-{name}.service"

    def timer_path(self, name: str) -> Path:
        return self.units_dir / f"local81-{name}.timer"

    def list(self) -> list[ScheduleDef]:
        if not self.root.exists():
            return []
        defs = []
        for path in sorted(self.root.glob("*.json")):
            defs.append(ScheduleDef.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return defs

    def load(self, name: str) -> ScheduleDef:
        path = self.def_path(name)
        if not path.exists():
            raise ScheduleError(f"no schedule named {name!r}")
        return ScheduleDef.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, defn: ScheduleDef) -> list[Path]:
        validate(defn)
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.units_dir.mkdir(parents=True, exist_ok=True)
        self.units_dir.chmod(0o700)

        written: list[Path] = []
        defn_path = self.def_path(defn.name)
        defn_path.write_text(json.dumps(defn.to_dict(), indent=2) + "\n", encoding="utf-8")
        defn_path.chmod(0o600)
        written.append(defn_path)

        wrapper = self.wrapper_path(defn.name)
        wrapper.write_text(render_wrapper(defn, lock_path=self.lock_path(defn.name)), encoding="utf-8")
        wrapper.chmod(0o700)
        written.append(wrapper)

        for path, text in (
            (self.service_path(defn.name), render_service_unit(defn, wrapper_path=wrapper)),
            (self.timer_path(defn.name), render_timer_unit(defn)),
        ):
            path.write_text(text, encoding="utf-8")
            path.chmod(0o600)
            written.append(path)
        return written

    def remove(self, name: str) -> list[Path]:
        removed: list[Path] = []
        for path in (
            self.def_path(name),
            self.wrapper_path(name),
            self.service_path(name),
            self.timer_path(name),
        ):
            if path.exists():
                path.unlink()
                removed.append(path)
        if not removed:
            raise ScheduleError(f"no schedule named {name!r}")
        return removed


# --- unit rendering --------------------------------------------------------


def render_wrapper(defn: ScheduleDef, *, lock_path: Path) -> str:
    quoted = " ".join(shlex.quote(part) for part in defn.command)
    return (
        "#!/bin/sh\n"
        "# Rendered by local81 schedule; runs under flock so timer fires never overlap.\n"
        "set -eu\n"
        f"exec flock -n {shlex.quote(str(lock_path))} {quoted}\n"
    )


def render_service_unit(defn: ScheduleDef, *, wrapper_path: Path) -> str:
    desc = defn.description or f"Local-81 scheduled task {defn.name}"
    lines = [
        "[Unit]",
        f"Description={desc}",
        "",
        "[Service]",
        "Type=oneshot",
        f"ExecStart={wrapper_path}",
    ]
    if defn.working_dir:
        lines.append(f"WorkingDirectory={defn.working_dir}")
    if defn.notify_url:
        # Best-effort fire-and-forget; never fail the run because the hook is down.
        curl = (
            f"/bin/sh -c 'curl -fsS -m 10 -X POST "
            f"-H \"Content-Type: application/json\" "
            f"-d \"{{\\\"schedule\\\":\\\"{defn.name}\\\",\\\"status\\\":\\\"done\\\"}}\" "
            f"{shlex.quote(defn.notify_url)} || true'"
        )
        lines.append(f"ExecStartPost={curl}")
    lines.append("")
    return "\n".join(lines)


def render_timer_unit(defn: ScheduleDef) -> str:
    desc = defn.description or f"Local-81 scheduled task {defn.name}"
    return "\n".join(
        [
            "[Unit]",
            f"Description={desc} (timer)",
            "",
            "[Timer]",
            f"OnCalendar={defn.on_calendar}",
            "Persistent=true",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ]
    )


def install_hint(store: ScheduleStore, name: str) -> str:
    service = store.service_path(name)
    timer = store.timer_path(name)
    unit = timer.name
    return (
        "Operator install (run as root on the control node):\n"
        f"  sudo cp {service} {timer} /etc/systemd/system/\n"
        "  sudo systemctl daemon-reload\n"
        f"  sudo systemctl enable --now {unit}\n"
        f"  systemctl list-timers {unit}"
    )
