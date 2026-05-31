from __future__ import annotations

import json
from pathlib import Path

from local81.commands.status import load_status_record, render_status


def test_status_no_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".local81" / "runs").mkdir(parents=True)
    out = render_status()
    assert "Local-81 status" in out
    assert "None right now" in out
    assert "No completed runs found yet" in out


def test_status_reads_latest_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / ".local81" / "runs" / "20260101T000000Z-99999"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "20260101T000000Z-99999",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "rc": 0
    }), encoding="utf-8")
    record = load_status_record()
    assert record.run_id == "20260101T000000Z-99999"
    assert record.result == "pass"


def test_status_reads_home_state(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    (home / ".local81").mkdir(parents=True)
    (home / ".local81" / "state.json").write_text(json.dumps({
        "last_run_id": "state-run-001",
        "last_result": "pass",
        "last_run_at": "2026-03-01T12:00:00Z",
        "last_rc": 0
    }), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    record = load_status_record()
    assert record.run_id == "state-run-001"
    assert record.result == "pass"
