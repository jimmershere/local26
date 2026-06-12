from __future__ import annotations

import json
from pathlib import Path

from local81.commands.rollback import run_rollback


def _write_run(runs_dir: Path, run_id: str, steps: list[dict]) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "local81.run.v0.1",
        "run_id": run_id,
        "plan_id": "plan-1",
        "rc": 0,
        "dry_run": False,
        "steps": steps,
    }
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")


def _restorable(sid: str, cmd: str) -> dict:
    return {
        "id": sid,
        "host": "web1",
        "type": "rsync",
        "rc": 0,
        "reversible": True,
        "rollback": {"type": "restore", "cmd": cmd},
    }


def test_rollback_run_not_found(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    rc = run_rollback("nope", runs_dir=str(runs_dir))
    assert rc == 1
    assert "Run not found" in capsys.readouterr().out


def test_rollback_nothing_reversible(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir, "r1", [{"id": "s1", "type": "rsync", "rc": 0, "converged": True}])
    rc = run_rollback("r1", runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Nothing to roll back" in out


def test_rollback_dry_run_shows_plan_no_record(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir, "r1", [_restorable("s1", "true")])
    rc = run_rollback("r1", runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Dry run" in out
    assert "[restore] s1" in out
    # No new rollback run directory created.
    assert {p.name for p in runs_dir.iterdir()} == {"r1"}


def test_rollback_execute_writes_record(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir, "r1", [_restorable("s1", "true"), _restorable("s2", "true")])
    rc = run_rollback("r1", execute=True, runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert "completed" in out
    new_dirs = [p for p in runs_dir.iterdir() if p.name != "r1"]
    assert len(new_dirs) == 1
    record = json.loads((new_dirs[0] / "rollback.json").read_text(encoding="utf-8"))
    assert record["schema"] == "local81.rollback.v0.1"
    assert record["source_run_id"] == "r1"
    assert len(record["restored"]) == 2
    assert all(r["rc"] == 0 for r in record["restored"])
    # LIFO: s2 restored before s1.
    assert [r["original_id"] for r in record["restored"]] == ["s2", "s1"]


def test_rollback_execute_reports_failure(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir, "r1", [_restorable("s1", "false")])
    rc = run_rollback("r1", execute=True, runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc != 0
    assert "failures" in out
    new_dirs = [p for p in runs_dir.iterdir() if p.name != "r1"]
    record = json.loads((new_dirs[0] / "rollback.json").read_text(encoding="utf-8"))
    assert record["rc"] != 0
    assert record["restored"][0]["rc"] != 0
