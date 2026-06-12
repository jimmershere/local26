"""Garbage-collect old run artifacts under .local81/runs/.

Run directories accumulate forever otherwise. ``gc`` enforces retention by
*count* (keep the newest N) and/or *age* (drop anything older than D days).
Following the project convention for mutating actions, it is **dry-run unless
``--execute``**: by default it only reports what it would remove.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunDir:
    path: Path
    mtime: float


def _list_run_dirs(runs_dir: Path) -> list[RunDir]:
    if not runs_dir.is_dir():
        return []
    out = []
    for child in runs_dir.iterdir():
        if child.is_dir():
            out.append(RunDir(path=child, mtime=child.stat().st_mtime))
    return out


def select_runs_to_prune(
    runs: list[RunDir], *, keep: int | None, max_age_days: int | None, now: float
) -> list[RunDir]:
    """Pure retention policy: newest-first, keep N, then drop those too old.

    A run survives only if it is within the newest ``keep`` *and* (when
    ``max_age_days`` is set) younger than the age cutoff. Either bound may be
    ``None`` to disable it; with both ``None`` nothing is pruned.
    """
    if keep is None and max_age_days is None:
        return []
    ordered = sorted(runs, key=lambda r: r.mtime, reverse=True)
    doomed: list[RunDir] = []
    cutoff = now - max_age_days * 86400 if max_age_days is not None else None
    for index, run in enumerate(ordered):
        too_many = keep is not None and index >= keep
        too_old = cutoff is not None and run.mtime < cutoff
        if too_many or too_old:
            doomed.append(run)
    return doomed


def run_gc(*, keep: int | None = None, max_age_days: int | None = None,
           execute: bool = False, runs_dir: str = ".local81/runs") -> int:
    if keep is None and max_age_days is None:
        print("Nothing to do: pass --keep N and/or --max-age-days D to set a retention policy.")
        return 0
    runs_path = Path(runs_dir)
    runs = _list_run_dirs(runs_path)
    now = datetime.now(timezone.utc).timestamp()
    doomed = select_runs_to_prune(runs, keep=keep, max_age_days=max_age_days, now=now)

    print("Local-81 run garbage collection")
    print("============")
    bound = []
    if keep is not None:
        bound.append(f"keep newest {keep}")
    if max_age_days is not None:
        bound.append(f"drop older than {max_age_days}d")
    print(f"Policy: {', '.join(bound)}")
    print(f"Total runs: {len(runs)}   To remove: {len(doomed)}   Surviving: {len(runs) - len(doomed)}\n")

    if not doomed:
        print("No runs match the retention policy. Nothing to remove.")
        return 0

    for run in sorted(doomed, key=lambda r: r.path.name):
        print(f"  {'removed' if execute else 'would remove'}: {run.path.name}")
        if execute:
            shutil.rmtree(run.path)

    if not execute:
        print("\nDry run: no directories deleted. Re-run with --execute to apply.")
    else:
        print(f"\nRemoved {len(doomed)} run director{'y' if len(doomed) == 1 else 'ies'}.")
    return 0
