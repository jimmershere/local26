from __future__ import annotations

from local81.rollback import (
    build_rollback_plan,
    reversible_steps,
    render_rollback_summary,
)


def _restorable_step(sid: str = "s1") -> dict:
    return {
        "id": sid,
        "host": "web1",
        "type": "rsync",
        "rc": 0,
        "reversible": True,
        "rollback": {"type": "restore", "cmd": f"cp -a backup-{sid} live-{sid}"},
    }


def test_restorable_step_is_classified_restore() -> None:
    plan = build_rollback_plan({"steps": [_restorable_step()]})
    assert len(plan) == 1
    step = plan[0]
    assert step.action == "restore"
    assert step.reversible is True
    assert step.cmd == "cp -a backup-s1 live-s1"
    assert step.rollback_type == "restore"


def test_plan_is_lifo() -> None:
    steps = [_restorable_step("a"), _restorable_step("b"), _restorable_step("c")]
    plan = build_rollback_plan({"steps": steps})
    assert [s.original_id for s in plan] == ["c", "b", "a"]


def test_skipped_step_not_reversible() -> None:
    step = {"id": "sk", "host": "web1", "type": "rsync", "rc": -1}
    plan = build_rollback_plan({"steps": [step]})
    assert plan[0].action == "skip"
    assert "skipped" in plan[0].reason


def test_failed_step_not_reversible() -> None:
    step = {"id": "f", "host": "web1", "type": "remote_cmd", "rc": 3}
    plan = build_rollback_plan({"steps": [step]})
    assert plan[0].action == "skip"
    assert "did not succeed" in plan[0].reason
    assert "rc=3" in plan[0].reason


def test_converged_step_not_reversible() -> None:
    step = {"id": "c", "host": "web1", "type": "rsync", "rc": 0, "converged": True}
    plan = build_rollback_plan({"steps": [step]})
    assert plan[0].action == "skip"
    assert "made no change" in plan[0].reason


def test_rsync_without_backup_explains_disabled_backup() -> None:
    step = {"id": "nb", "host": "web1", "type": "rsync", "rc": 0, "reversible": False}
    plan = build_rollback_plan({"steps": [step]})
    assert plan[0].action == "skip"
    assert "no backup was recorded" in plan[0].reason


def test_raw_command_step_not_reversible() -> None:
    step = {"id": "raw", "host": "web1", "type": "remote_cmd", "rc": 0}
    plan = build_rollback_plan({"steps": [step]})
    assert plan[0].action == "skip"
    assert "no recorded reverse command" in plan[0].reason


def test_reversible_steps_filters_restores_only() -> None:
    steps = [
        _restorable_step("a"),
        {"id": "b", "type": "rsync", "rc": 0, "converged": True},
        _restorable_step("c"),
    ]
    plan = build_rollback_plan({"steps": steps})
    restores = reversible_steps(plan)
    assert [s.original_id for s in restores] == ["c", "a"]


def test_render_summary_lists_restores_and_skips() -> None:
    steps = [
        _restorable_step("a"),
        {"id": "b", "type": "rsync", "rc": 0, "converged": True},
    ]
    plan = build_rollback_plan({"steps": steps})
    text = render_rollback_summary({"run_id": "run-1", "plan_id": "plan-1"}, plan)
    assert "Reversible steps: 1" in text
    assert "Non-rollbackable: 1" in text
    assert "[restore] a" in text
    assert "[skip] b" in text
    assert "run-1" in text


def test_empty_manifest_yields_empty_plan() -> None:
    plan = build_rollback_plan({})
    assert plan == []
    assert reversible_steps(plan) == []
