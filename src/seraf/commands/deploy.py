from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class StepResult:
    id: str
    rc: int
    started_at: str
    finished_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_shell(command: str) -> int:
    proc = subprocess.run(["bash", "-lc", command], text=True)
    return proc.returncode


def _write_run(run_path: Path, payload: dict) -> None:
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def run_deploy(*, plan: str, scope: str | None = None, max_parallel: int = 1, rollback_on_failure: bool = False) -> int:
    plan_data = _load_plan(Path(plan))
    scopes = plan_data.get("scopes", [])
    if scope:
        scopes = [s for s in scopes if s.get("scope") == scope]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-deploy"
    run_dir = Path(".seraf") / "runs" / run_id
    run_json = run_dir / "run.json"
    steps_out: list[dict] = []
    successful_with_rollback: list[dict] = []
    failure_seen = False
    rc = 0

    for scope_obj in scopes:
        for step in scope_obj.get("steps", []):
            started = _now_iso()
            step_rc = _run_shell(step["cmd"])
            finished = _now_iso()
            steps_out.append({
                "id": step["id"],
                "rc": step_rc,
                "started_at": started,
                "finished_at": finished,
            })
            if step_rc == 0:
                if step.get("rollback") and step["rollback"].get("cmd"):
                    successful_with_rollback.append(step)
                continue

            failure_seen = True
            rc = step_rc or 1

            on_failure = step.get("on_failure") or {}
            if on_failure.get("cmd"):
                _run_shell(on_failure["cmd"])

            if rollback_on_failure:
                for prev in reversed(successful_with_rollback):
                    rollback = prev.get("rollback") or {}
                    if rollback.get("cmd"):
                        _run_shell(rollback["cmd"])

            global_failure = plan_data.get("on_failure") or {}
            if global_failure.get("cmd"):
                _run_shell(global_failure["cmd"])
            break
        if failure_seen:
            break

    payload = {
        "schema": "seraf.run.v0.1",
        "run_id": run_id,
        "plan_id": plan_data.get("plan_id"),
        "started_at": steps_out[0]["started_at"] if steps_out else _now_iso(),
        "finished_at": _now_iso(),
        "rc": rc,
        "steps": steps_out,
    }
    _write_run(run_json, payload)
    return rc
