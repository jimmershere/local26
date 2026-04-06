from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class StatusRecord:
    run_id: str | None
    result: str | None
    last_run_at: str | None
    last_rc: int | None


def _result_from_rc(rc: int | None) -> str | None:
    if rc is None:
        return None
    return "pass" if rc == 0 else "fail"


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_status_record() -> StatusRecord:
    home_state = Path.home() / ".seraf" / "state.json"
    if home_state.is_file():
        data = _load_json(home_state) or {}
        return StatusRecord(
            run_id=data.get("last_run_id"),
            result=data.get("last_result"),
            last_run_at=data.get("last_run_at"),
            last_rc=data.get("last_rc"),
        )

    tmp_state = Path("/tmp/seraf-state.json")
    if tmp_state.is_file():
        data = _load_json(tmp_state) or {}
        return StatusRecord(
            run_id=data.get("last_run_id"),
            result=data.get("last_result"),
            last_run_at=data.get("last_run_at"),
            last_rc=data.get("last_rc"),
        )

    runs_dir = Path(".seraf") / "runs"
    if runs_dir.is_dir():
        run_files = sorted(runs_dir.glob("*/run.json"))
        if run_files:
            latest = run_files[-1]
            data = _load_json(latest) or {}
            rc = data.get("rc")
            return StatusRecord(
                run_id=data.get("run_id"),
                result=_result_from_rc(rc),
                last_run_at=data.get("finished_at") or data.get("started_at"),
                last_rc=rc,
            )

    return StatusRecord(run_id=None, result=None, last_run_at=None, last_rc=None)


def render_status() -> str:
    record = load_status_record()
    lines = [
        "=== seraf status ===",
        "",
        "Active runs:",
        "  (none)",
        "",
        "Last run:",
    ]
    if not record.run_id:
        lines.append("  (no runs found)")
    else:
        lines.extend([
            f"  run_id    : {record.run_id}",
            f"  result    : {record.result or '(unknown)'}",
            f"  exit_code : {record.last_rc if record.last_rc is not None else '(unknown)'}",
            f"  timestamp : {record.last_run_at or '(unknown)'}",
        ])
    return "\n".join(lines)


def run_status() -> int:
    print(render_status())
    return 0
