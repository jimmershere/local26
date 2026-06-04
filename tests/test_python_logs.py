from __future__ import annotations

import json
from pathlib import Path

from local81.commands.logs import render_run_log, run_logs, _find_run


def _make_run(runs_dir: Path, run_id: str, *, rc: int = 0) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "local81.run.v0.1",
        "run_id": run_id,
        "plan_id": "plan-1",
        "started_at": "2026-04-01T10:00:00Z",
        "finished_at": "2026-04-01T10:01:30Z",
        "rc": rc,
        "dry_run": False,
        "steps": [
            {"id": "s1", "type": "rsync", "host": "web1", "cmd": "echo hello",
             "rc": rc, "started_at": "2026-04-01T10:00:00Z",
             "finished_at": "2026-04-01T10:01:30Z", "stdout": "hello", "stderr": ""},
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# _find_run
# ---------------------------------------------------------------------------

def test_find_run_exact(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    found = _find_run("20260401T100000Z-deploy", runs_dir=str(runs_dir))
    assert found is not None
    assert found.name == "run.json"


def test_find_run_prefix(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    found = _find_run("20260401", runs_dir=str(runs_dir))
    assert found is not None


def test_find_run_missing(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    found = _find_run("nope", runs_dir=str(runs_dir))
    assert found is None


def test_find_run_no_dir(tmp_path: Path) -> None:
    found = _find_run("nope", runs_dir=str(tmp_path / "nodir"))
    assert found is None


# ---------------------------------------------------------------------------
# render_run_log
# ---------------------------------------------------------------------------

def test_render_run_log_not_found(tmp_path: Path) -> None:
    out = render_run_log("missing", runs_dir=str(tmp_path / "nope"))
    assert "Run not found" in out


def test_render_run_log_shows_details(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    out = render_run_log("20260401T100000Z-deploy", runs_dir=str(runs_dir))
    assert "Local-81 run log" in out
    assert "Run ID:" in out
    assert "20260401T100000Z-deploy" in out
    assert "PASS" in out
    assert "echo hello" in out
    assert "stdout: hello" in out


def test_render_run_log_failed(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy", rc=3)
    out = render_run_log("20260401T100000Z-deploy", runs_dir=str(runs_dir))
    assert "FAIL" in out
    assert "Exit code: 3" in out


def test_render_run_log_with_hosts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "20260401T100000Z-deploy"
    run_dir.mkdir(parents=True)
    data = {
        "run_id": "20260401T100000Z-deploy",
        "plan_id": "p1",
        "started_at": "2026-04-01T10:00:00Z",
        "finished_at": "2026-04-01T10:01:00Z",
        "rc": 0,
        "dry_run": False,
        "steps": [],
        "hosts": [
            {"host": "alpha", "rc": 0, "deployed_files": 2},
            {"host": "beta", "rc": 0, "deployed_files": 1},
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")
    out = render_run_log("20260401T100000Z-deploy", runs_dir=str(runs_dir))
    assert "alpha" in out
    assert "beta" in out


# ---------------------------------------------------------------------------
# run_logs
# ---------------------------------------------------------------------------

def test_run_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    runs_dir = tmp_path / ".local81" / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    monkeypatch.chdir(tmp_path)
    rc = run_logs("20260401T100000Z-deploy")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Local-81 run log" in out
