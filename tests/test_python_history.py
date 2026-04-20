from __future__ import annotations

import json
from pathlib import Path

from seraf.commands.history import list_runs, render_history, run_history


def _make_run(runs_dir: Path, run_id: str, *, rc: int = 0, dry_run: bool = False,
              steps: list | None = None, hosts: list | None = None) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "seraf.run.v0.1",
        "run_id": run_id,
        "plan_id": "plan-1",
        "started_at": "2026-04-01T10:00:00Z",
        "finished_at": "2026-04-01T10:01:30Z",
        "rc": rc,
        "dry_run": dry_run,
        "steps": steps or [
            {"id": "s1", "type": "rsync", "host": "web1", "cmd": "echo ok",
             "rc": rc, "started_at": "2026-04-01T10:00:00Z",
             "finished_at": "2026-04-01T10:01:30Z", "stdout": "ok", "stderr": ""},
        ],
    }
    if hosts:
        data["hosts"] = hosts
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------

def test_list_runs_empty(tmp_path: Path) -> None:
    runs = list_runs(runs_dir=str(tmp_path / "nope"))
    assert runs == []


def test_list_runs_single(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    runs = list_runs(runs_dir=str(runs_dir))
    assert len(runs) == 1
    assert runs[0]["run_id"] == "20260401T100000Z-deploy"
    assert runs[0]["status"] == "pass"
    assert runs[0]["duration"] == "1m30s"


def test_list_runs_multiple_sorted(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    _make_run(runs_dir, "20260402T100000Z-deploy", rc=1)
    runs = list_runs(runs_dir=str(runs_dir))
    assert len(runs) == 2
    # Newest first
    assert runs[0]["run_id"] == "20260402T100000Z-deploy"
    assert runs[0]["status"] == "fail"


def test_list_runs_limit(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    for i in range(5):
        _make_run(runs_dir, f"2026040{i+1}T100000Z-deploy")
    runs = list_runs(runs_dir=str(runs_dir), limit=3)
    assert len(runs) == 3


def test_list_runs_with_hosts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy",
              hosts=[{"host": "alpha", "rc": 0, "deployed_files": 2},
                     {"host": "beta", "rc": 0, "deployed_files": 1}])
    runs = list_runs(runs_dir=str(runs_dir))
    assert "alpha" in runs[0]["hosts"]
    assert "beta" in runs[0]["hosts"]


def test_list_runs_errors(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy", rc=7, steps=[
        {"id": "s1", "type": "rsync", "host": "web1", "cmd": "echo fail",
         "rc": 7, "started_at": "2026-04-01T10:00:00Z",
         "finished_at": "2026-04-01T10:01:30Z", "stdout": "", "stderr": "connection refused"},
    ])
    runs = list_runs(runs_dir=str(runs_dir))
    assert "connection refused" in runs[0]["errors"]


# ---------------------------------------------------------------------------
# render_history
# ---------------------------------------------------------------------------

def test_render_history_empty(tmp_path: Path) -> None:
    out = render_history(runs_dir=str(tmp_path / "nope"))
    assert "No runs found" in out


def test_render_history_shows_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    _make_run(runs_dir, "20260402T100000Z-deploy", rc=1, dry_run=True)
    out = render_history(runs_dir=str(runs_dir))
    assert "[PASS]" in out
    assert "[FAIL]" in out
    assert "(dry run)" in out
    assert "Duration:" in out


# ---------------------------------------------------------------------------
# run_history (capsys)
# ---------------------------------------------------------------------------

def test_run_history(tmp_path: Path, monkeypatch, capsys) -> None:
    runs_dir = tmp_path / ".seraf" / "runs"
    _make_run(runs_dir, "20260401T100000Z-deploy")
    monkeypatch.chdir(tmp_path)
    rc = run_history()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Seraf history" in out
    assert "20260401T100000Z-deploy" in out
