from __future__ import annotations

import json
from pathlib import Path


def _find_run(run_id: str, runs_dir: str = ".local26/runs") -> Path | None:
    """Find the run.json file for a given run ID (exact or prefix match)."""
    runs_path = Path(runs_dir)
    if not runs_path.is_dir():
        return None
    exact = runs_path / run_id / "run.json"
    if exact.is_file():
        return exact
    # Prefix match
    candidates = sorted(runs_path.glob("*/run.json"))
    matches = [c for c in candidates if c.parent.name.startswith(run_id)]
    if len(matches) == 1:
        return matches[0]
    return None


def render_run_log(run_id: str, *, runs_dir: str = ".local26/runs") -> str:
    """Render full output for a single run."""
    run_file = _find_run(run_id, runs_dir)
    if not run_file:
        return f"Run not found: {run_id}\nCheck 'local26 history' for available run IDs."

    try:
        data = json.loads(run_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"Failed to read run file: {exc}"

    lines = [
        "Local-26 run log",
        "=============",
        f"Run ID:    {data.get('run_id', run_id)}",
        f"Plan ID:   {data.get('plan_id', 'n/a')}",
        f"Status:    {'PASS' if data.get('rc', -1) == 0 else 'FAIL'}",
        f"Exit code: {data.get('rc')}",
        f"Dry run:   {data.get('dry_run', False)}",
        f"Started:   {data.get('started_at', 'n/a')}",
        f"Finished:  {data.get('finished_at', 'n/a')}",
        "",
    ]

    if "hosts" in data and isinstance(data["hosts"], list):
        lines.append("Hosts:")
        for h in data["hosts"]:
            status = "ok" if h.get("rc", -1) == 0 else f"FAILED (rc={h.get('rc')})"
            lines.append(f"  {h.get('host', '?')}: {status} ({h.get('deployed_files', 0)} files)")
        lines.append("")

    steps = data.get("steps", [])
    lines.append(f"Steps ({len(steps)}):")
    lines.append("-" * 60)
    for step in steps:
        tag = "OK" if step.get("rc", -1) == 0 else ("SKIP" if step.get("rc") == -1 else "FAIL")
        lines.append(f"[{tag}] {step.get('id', '?')} [{step.get('type', 'step')}] on {step.get('host', 'n/a')}")
        lines.append(f"  Command: {step.get('cmd', 'n/a')}")
        lines.append(f"  RC: {step.get('rc')}  |  {step.get('started_at', '?')} -> {step.get('finished_at', '?')}")
        if step.get("stdout"):
            for out_line in step["stdout"].splitlines()[:10]:
                lines.append(f"  stdout: {out_line}")
        if step.get("stderr"):
            for err_line in step["stderr"].splitlines()[:10]:
                lines.append(f"  stderr: {err_line}")
        lines.append("")

    return "\n".join(lines)


def run_logs(run_id: str) -> int:
    print(render_run_log(run_id))
    return 0
