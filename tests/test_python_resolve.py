from __future__ import annotations

import hashlib
from pathlib import Path

from local81.connectors import LocalConnector
from local81.models import CommandResult
from local81.resolve import resolve_step_action


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_step(path: str, sha: str | None) -> dict:
    intent = {"path": path}
    if sha is not None:
        intent["sha256"] = sha
    return {"id": "s1", "type": "rsync", "op": "file.synced", "intent": intent, "host": "@local", "cmd": f"rsync -- src {path}"}


class _BoomConnector:
    name = "@boom"

    def run(self, command, *, timeout_seconds=None, env=None) -> CommandResult:
        raise OSError("connection refused")


# --------------------------------------------------------------------------- #
# opt-in: non-op steps are never gated
# --------------------------------------------------------------------------- #
def test_raw_command_step_is_not_resolved():
    step = {"id": "s1", "type": "remote_cmd", "host": "h1", "cmd": "systemctl restart app"}
    action, observed = resolve_step_action(step)
    assert action is None and observed is None


# --------------------------------------------------------------------------- #
# file.synced against a real local filesystem
# --------------------------------------------------------------------------- #
def test_file_synced_converged_is_none(tmp_path: Path):
    target = tmp_path / "app.conf"
    target.write_text("hello\n", encoding="utf-8")
    step = _file_step(str(target), _sha256("hello\n"))
    action, observed = resolve_step_action(step, connector=LocalConnector())
    assert action == "none"
    assert observed["exists"] is True


def test_file_synced_absent_is_create(tmp_path: Path):
    step = _file_step(str(tmp_path / "nope.conf"), _sha256("hello\n"))
    action, _ = resolve_step_action(step, connector=LocalConnector())
    assert action == "create"


def test_file_synced_content_drift_is_update(tmp_path: Path):
    target = tmp_path / "app.conf"
    target.write_text("OLD CONTENT\n", encoding="utf-8")
    # Plan was built when the desired content hashed to the "new" value.
    step = _file_step(str(target), _sha256("NEW CONTENT\n"))
    action, observed = resolve_step_action(step, connector=LocalConnector())
    assert action == "update"
    assert observed["sha256"] == _sha256("OLD CONTENT\n")


# --------------------------------------------------------------------------- #
# dir.present against a real local filesystem
# --------------------------------------------------------------------------- #
def test_dir_present_converged_is_none(tmp_path: Path):
    step = {"id": "d1", "type": "mkdir", "op": "dir.present", "intent": {"path": str(tmp_path)}, "host": "@local", "cmd": "mkdir -p"}
    action, _ = resolve_step_action(step, connector=LocalConnector())
    assert action == "none"


def test_dir_present_absent_is_create(tmp_path: Path):
    step = {"id": "d1", "type": "mkdir", "op": "dir.present", "intent": {"path": str(tmp_path / "missing")}, "host": "@local", "cmd": "mkdir -p"}
    action, _ = resolve_step_action(step, connector=LocalConnector())
    assert action == "create"


# --------------------------------------------------------------------------- #
# convergence: a real push, then a second pass is a no-op
# --------------------------------------------------------------------------- #
def test_convergence_second_pass_is_none(tmp_path: Path):
    target = tmp_path / "deployed.txt"
    desired = "payload v1\n"
    step = _file_step(str(target), _sha256(desired))

    # First pass: file absent -> must run.
    first, _ = resolve_step_action(step, connector=LocalConnector())
    assert first == "create"

    # Simulate the push landing the desired bytes, then re-resolve.
    target.write_text(desired, encoding="utf-8")
    second, _ = resolve_step_action(step, connector=LocalConnector())
    assert second == "none"


# --------------------------------------------------------------------------- #
# drift guard: target changed out from under the plan -> still applies
# --------------------------------------------------------------------------- #
def test_drift_guard_rewrites_changed_target(tmp_path: Path):
    target = tmp_path / "deployed.txt"
    desired = "payload v2\n"
    target.write_text(desired, encoding="utf-8")
    step = _file_step(str(target), _sha256(desired))
    assert resolve_step_action(step, connector=LocalConnector())[0] == "none"

    # Someone edited the file on the host after the plan converged.
    target.write_text("hand-edited drift\n", encoding="utf-8")
    assert resolve_step_action(step, connector=LocalConnector())[0] == "update"


# --------------------------------------------------------------------------- #
# fail-open: a broken probe never hides a needed change
# --------------------------------------------------------------------------- #
def test_probe_failure_is_fail_open():
    step = _file_step("/srv/app.conf", _sha256("x"))
    action, observed = resolve_step_action(step, connector=_BoomConnector())
    assert action == "unknown"
    assert "error" in observed


# --------------------------------------------------------------------------- #
# fail-open: a file.synced step with no desired sha256 must never skip a push
# --------------------------------------------------------------------------- #
def test_file_synced_without_sha_is_fail_open(tmp_path: Path):
    # Source was unreadable at plan time, so the step carries no sha256. Even
    # though the target already exists, we cannot prove convergence -> run it.
    target = tmp_path / "app.conf"
    target.write_text("whatever\n", encoding="utf-8")
    step = _file_step(str(target), None)
    action, observed = resolve_step_action(step, connector=LocalConnector())
    assert action == "unknown"
    assert "reason" in observed
