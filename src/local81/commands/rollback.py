from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from local81.commands.deploy import _run_shell
from local81.commands.logs import _find_run
from local81.rollback import build_rollback_plan, render_rollback_summary, reversible_steps


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_rollback(run_id: str, *, execute: bool = False, runs_dir: str = ".local81/runs") -> int:
    run_file = _find_run(run_id, runs_dir)
    if not run_file:
        print(f"Run not found: {run_id}\nCheck 'local81 history' for available run IDs.")
        return 1
    try:
        manifest = json.loads(run_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to read run file: {exc}")
        return 1

    plan = build_rollback_plan(manifest)
    print(render_rollback_summary(manifest, plan))

    restores = reversible_steps(plan)
    if not restores:
        print("Nothing to roll back: no reversible steps were recorded for this run.")
        return 0

    if not execute:
        print("Dry run: no changes made. Re-run with --execute to apply the rollback.")
        return 0

    source_run = manifest.get("run_id", run_id)
    new_run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-rollback"
    new_run_dir = Path(runs_dir) / new_run_id
    new_run_dir.mkdir(parents=True, exist_ok=True)
    new_run_dir.chmod(0o700)

    records: list[dict] = []
    overall_rc = 0
    print(f"\nApplying rollback (run {new_run_id}):")
    for step in restores:
        started = _now_iso()
        rc, stdout, stderr, _timed_out = _run_shell(step.cmd or "", dry_run=False)
        finished = _now_iso()
        status = "ok" if rc == 0 else f"FAILED (rc={rc})"
        print(f"  [restore] {step.original_id}: {status}")
        if rc != 0:
            overall_rc = rc or 1
            if stderr:
                print(f"            {stderr.strip()}")
        records.append({
            "original_id": step.original_id,
            "host": step.host,
            "cmd": step.cmd,
            "rollback_type": step.rollback_type,
            "rc": rc,
            "started_at": started,
            "finished_at": finished,
            "stdout": stdout,
            "stderr": stderr,
        })

    manifest_out = {
        "schema": "local81.rollback.v0.1",
        "run_id": new_run_id,
        "source_run_id": source_run,
        "started_at": records[0]["started_at"] if records else _now_iso(),
        "finished_at": _now_iso(),
        "rc": overall_rc,
        "restored": records,
        "skipped": [
            {"original_id": s.original_id, "reason": s.reason}
            for s in plan if s.action == "skip"
        ],
    }
    out_file = new_run_dir / "rollback.json"
    out_file.write_text(json.dumps(manifest_out, indent=2) + "\n", encoding="utf-8")
    out_file.chmod(0o600)
    print(f"\nRollback {'completed' if overall_rc == 0 else 'finished with failures'}. Record: {out_file}")
    return overall_rc
