from __future__ import annotations

import json
from pathlib import Path

from local26.cli import build_parser
from local26.commands.diff import diff_plans, run_diff


def _write_plan(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _plan(plan_id: str, *, scopes: list[dict] | None = None, **overrides) -> dict:
    data = {
        "local26_version": "0.1",
        "kind": "plan",
        "mode": "deploy",
        "schema": "local26.plan.v0.1",
        "plan_id": plan_id,
        "created_at": "2026-04-01T10:00:00Z",
        "config_fingerprint": "sha256:abc123",
        "scopes": scopes or [],
    }
    data.update(overrides)
    return data


def test_diff_plans_identical(tmp_path: Path) -> None:
    plan_a = tmp_path / "a.json"
    plan_b = tmp_path / "b.json"
    data = _plan("plan-1", scopes=[{"scope": "api", "steps": []}])
    _write_plan(plan_a, data)
    _write_plan(plan_b, data)

    out = diff_plans(str(plan_a), str(plan_b))

    assert "Local-26 plan diff" in out
    assert "Scope 'api': no changes" in out


def test_diff_plans_reports_metadata_scope_and_step_changes(tmp_path: Path) -> None:
    plan_a = tmp_path / "a.json"
    plan_b = tmp_path / "b.json"
    _write_plan(
        plan_a,
        _plan(
            "plan-a",
            scopes=[
                {
                    "scope": "api",
                    "inputs": {"target_dir": "/srv/api", "servers": ["api1"]},
                    "discovery": {"files_selected": 1},
                    "steps": [
                        {"id": "scope:api:0001", "type": "rsync", "host": "api1", "cmd": "echo old"},
                        {"id": "scope:api:0002", "type": "mkdir", "host": "api1", "cmd": "mkdir -p /srv/api"},
                    ],
                },
                {"scope": "web", "steps": []},
            ],
        ),
    )
    _write_plan(
        plan_b,
        _plan(
            "plan-b",
            created_at="2026-04-02T10:00:00Z",
            config_fingerprint="sha256:def456",
            scopes=[
                {
                    "scope": "api",
                    "inputs": {"target_dir": "/opt/api", "servers": ["api1", "api2"]},
                    "discovery": {"files_selected": 2},
                    "steps": [
                        {"id": "scope:api:0001", "type": "remote_cmd", "host": "api2", "cmd": "echo new"},
                        {"id": "scope:api:0003", "type": "rsync", "host": "api2", "cmd": "rsync ..."},
                    ],
                },
                {"scope": "worker", "steps": [{"id": "scope:worker:0001", "type": "rsync"}]},
            ],
        ),
    )

    out = diff_plans(str(plan_a), str(plan_b))

    assert "Metadata changes:" in out
    assert "config_fingerprint: 'sha256:abc123' -> 'sha256:def456'" in out
    assert "Scope 'api':" in out
    assert "input target_dir: '/srv/api' -> '/opt/api'" in out
    assert "discovery files_selected: 1 -> 2" in out
    assert "step REMOVED: scope:api:0002 [mkdir]" in out
    assert "step ADDED: scope:api:0003 [rsync]" in out
    assert "step CHANGED: scope:api:0001 (cmd: 'echo old' -> 'echo new', host: 'api1' -> 'api2', type: 'rsync' -> 'remote_cmd')" in out
    assert "Scope 'web': REMOVED" in out
    assert "Scope 'worker': ADDED" in out


def test_diff_plans_load_failure(tmp_path: Path) -> None:
    plan_a = tmp_path / "a.json"
    plan_b = tmp_path / "b.json"
    plan_a.write_text("{not json", encoding="utf-8")
    _write_plan(plan_b, _plan("plan-b"))

    out = diff_plans(str(plan_a), str(plan_b))

    assert "Failed to load plan A" in out


def test_run_diff_prints_output(tmp_path: Path, capsys) -> None:
    plan_a = tmp_path / "a.json"
    plan_b = tmp_path / "b.json"
    data = _plan("plan-1")
    _write_plan(plan_a, data)
    _write_plan(plan_b, data)

    rc = run_diff(str(plan_a), str(plan_b))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Local-26 plan diff" in out


def test_diff_parser_accepts_plan_paths() -> None:
    parser = build_parser()
    args = parser.parse_args(["diff", "plan-a.json", "plan-b.json"])

    assert args.command == "diff"
    assert args.plan_a == "plan-a.json"
    assert args.plan_b == "plan-b.json"
