from __future__ import annotations

import json
from pathlib import Path


def _load_run(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _duration(started: str | None, finished: str | None) -> str:
    if not started or not finished:
        return "n/a"
    from datetime import datetime
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s = datetime.strptime(started, fmt)
        f = datetime.strptime(finished, fmt)
        delta = f - s
        total = int(delta.total_seconds())
        if total < 60:
            return f"{total}s"
        return f"{total // 60}m{total % 60}s"
    except Exception:
        return "n/a"


def _hosts_from_run(data: dict) -> str:
    """Extract a comma-separated host list from a run record."""
    if "hosts" in data and isinstance(data["hosts"], list):
        return ", ".join(h.get("host", "?") for h in data["hosts"])
    hosts_seen: list[str] = []
    seen: set[str] = set()
    for step in data.get("steps", []):
        host = step.get("host")
        if host and host not in seen:
            seen.add(host)
            hosts_seen.append(host)
    return ", ".join(hosts_seen) if hosts_seen else "n/a"


def _errors_from_run(data: dict) -> str:
    errors: list[str] = []
    for step in data.get("steps", []):
        if step.get("rc", 0) not in (0, -1):
            stderr = step.get("stderr", "")
            msg = stderr[:60] if stderr else f"rc={step['rc']}"
            errors.append(f"{step.get('id', '?')}: {msg}")
    return "; ".join(errors) if errors else ""


def list_runs(*, runs_dir: str = ".local81/runs", limit: int = 20) -> list[dict]:
    """Return recent run summaries, newest first."""
    runs_path = Path(runs_dir)
    if not runs_path.is_dir():
        return []
    run_files = sorted(runs_path.glob("*/run.json"), reverse=True)
    results: list[dict] = []
    for rf in run_files[:limit]:
        data = _load_run(rf)
        if not data:
            continue
        results.append({
            "run_id": data.get("run_id", rf.parent.name),
            "plan_id": data.get("plan_id"),
            "status": "pass" if data.get("rc", -1) == 0 else "fail",
            "rc": data.get("rc"),
            "dry_run": data.get("dry_run", False),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "duration": _duration(data.get("started_at"), data.get("finished_at")),
            "hosts": _hosts_from_run(data),
            "errors": _errors_from_run(data),
            "step_count": len(data.get("steps", [])),
        })
    return results


def render_history(*, runs_dir: str = ".local81/runs", limit: int = 20) -> str:
    runs = list_runs(runs_dir=runs_dir, limit=limit)
    lines = [
        "Local-81 history",
        "=============",
        "",
    ]
    if not runs:
        lines.append("No runs found yet.")
        lines.append("Deploy a plan first, then check back here.")
        return "\n".join(lines)

    for run in runs:
        tag = "PASS" if run["status"] == "pass" else "FAIL"
        dry = " (dry run)" if run["dry_run"] else ""
        lines.append(f"[{tag}] {run['run_id']}{dry}")
        lines.append(f"  Plan: {run['plan_id'] or 'n/a'}  |  Steps: {run['step_count']}  |  Duration: {run['duration']}")
        lines.append(f"  Hosts: {run['hosts']}")
        if run["errors"]:
            lines.append(f"  Errors: {run['errors']}")
        lines.append("")

    return "\n".join(lines)


def run_history(*, limit: int = 20) -> int:
    print(render_history(limit=limit))
    return 0
