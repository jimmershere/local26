from __future__ import annotations

import json
from pathlib import Path

from local26.cli import build_parser
from local26.commands.plan import run_plan


def _write_legacy_settings(path: Path, src_dir: Path) -> None:
    path.write_text(
        "[myapp]\n"
        f"source_dir = {src_dir}\n"
        "target_dir = /srv/app\n"
        "servers = testhost\n"
        "backup = false\n",
        encoding="utf-8",
    )


def _prepare_project(tmp_path: Path, monkeypatch) -> Path:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "file.txt").write_text("hello", encoding="utf-8")
    _write_legacy_settings(tmp_path / "settings.cfg", src_dir)
    monkeypatch.chdir(tmp_path)
    from local26.commands.init import run_init
    assert run_init(import_path="settings.cfg", force=True, project="demo") == 0
    state_path = tmp_path / ".local26" / "state" / "myapp.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["last_success"] = None
    state_path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    return src_dir


def test_run_plan_summary_outputs_step_lines_and_writes_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    _prepare_project(tmp_path, monkeypatch)
    capsys.readouterr()

    rc = run_plan(summary=True)
    out = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert out
    assert all(" | " in line for line in out)
    assert all(len(line.split(" | ")) == 4 for line in out)
    assert any(line.startswith("scope:myapp:") for line in out)
    assert all(line.endswith(" | pending") for line in out)
    assert list((tmp_path / ".local26" / "plans").glob("*.plan.json"))


def test_run_plan_summary_honors_ci_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    _prepare_project(tmp_path, monkeypatch)
    capsys.readouterr()

    rc = run_plan(summary=True, ci_mode=True)
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert "scope:myapp:" in out
    assert not list((tmp_path / ".local26" / "plans").glob("*.plan.json"))


def test_plan_parser_accepts_summary_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["plan", "--summary", "--scope", "myapp"])
    assert args.command == "plan"
    assert args.summary is True
    assert args.scope == "myapp"
