"""Rollback primitive: turn a completed run manifest into a reverse plan.

Local-81 already replays per-step ``rollback`` commands in LIFO order when a
deploy fails mid-run (``--rollback-on-failure``). This module adds the *after
the fact* case: given the ``run.json`` of a run that already finished, build an
ordered rollback plan so an operator can undo a deploy that succeeded but turned
out to be wrong.

Honesty is the whole point. A step is only marked reversible when the manifest
recorded a concrete rollback command for it (today: a ``cp -a`` restore from the
rsync ``--backup`` copy). Everything else — raw commands, steps that made no
change, steps that never completed — is surfaced as an explicit *skip* with a
reason, never silently treated as undone. We reverse exactly what we can prove
we can reverse, and we say so for the rest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RollbackStep:
    original_id: str
    host: str | None
    action: str  # "restore" or "skip"
    reversible: bool
    reason: str
    cmd: str | None = None
    rollback_type: str | None = None


def _classify(step: dict) -> RollbackStep:
    sid = step.get("id", "?")
    host = step.get("host")
    rc = step.get("rc")
    rollback = step.get("rollback") or {}

    if rc == -1:
        return RollbackStep(sid, host, "skip", False, "step was skipped during the run; nothing to undo")
    if rc not in (0, None) and rc != 0:
        return RollbackStep(sid, host, "skip", False, f"step did not succeed (rc={rc}); nothing to undo")
    if step.get("converged"):
        return RollbackStep(sid, host, "skip", False, "step was already converged and made no change")
    if step.get("reversible") and rollback.get("cmd"):
        return RollbackStep(
            sid, host, "restore", True,
            "restore from recorded backup",
            cmd=rollback["cmd"], rollback_type=rollback.get("type"),
        )
    step_type = step.get("type") or "step"
    if step_type == "rsync":
        reason = "no backup was recorded for this file (scope backup disabled); cannot auto-restore"
    else:
        reason = f"{step_type!r} step has no recorded reverse command; not auto-reversible"
    return RollbackStep(sid, host, "skip", False, reason)


def build_rollback_plan(manifest: dict) -> list[RollbackStep]:
    """Produce a LIFO rollback plan from a run manifest (``run.json`` contents)."""
    steps = manifest.get("steps", [])
    return [_classify(step) for step in reversed(steps)]


def reversible_steps(plan: list[RollbackStep]) -> list[RollbackStep]:
    return [s for s in plan if s.action == "restore"]


def render_rollback_summary(manifest: dict, plan: list[RollbackStep]) -> str:
    restores = reversible_steps(plan)
    skips = [s for s in plan if s.action == "skip"]
    lines = [
        "Local-81 rollback plan",
        "============",
        f"Source run: {manifest.get('run_id', '?')}  (plan {manifest.get('plan_id', 'n/a')})",
        f"Reversible steps: {len(restores)}   Non-rollbackable: {len(skips)}",
        "",
    ]
    if restores:
        lines.append("Will restore (in this order):")
        for s in restores:
            lines.append(f"  [restore] {s.original_id} on {s.host or 'local'}")
            lines.append(f"            {s.cmd}")
        lines.append("")
    if skips:
        lines.append("Will skip (non-rollbackable — left untouched):")
        for s in skips:
            lines.append(f"  [skip] {s.original_id}: {s.reason}")
        lines.append("")
    return "\n".join(lines)
