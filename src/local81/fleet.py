"""Fleet execution scheduler: rolling batches with a failure threshold.

This is the pure scheduling core behind ``deploy --forks/--serial/--max-fail``.
It is deliberately free of any deploy, SSH, or plan knowledge: it takes a list of
host identifiers and a ``runner`` callable (``host -> HostOutcome``) and decides
*which hosts run, in what batches, and when to stop*. The deploy command supplies
the runner that actually pushes files; tests supply a fake one. That separation
is what makes the failure-threshold logic unit-testable without a real fleet.

Scheduling model (pyinfra's taxonomy, Semaphore's rolling-update ergonomics):

* ``--forks N`` — at most ``N`` hosts execute concurrently within a batch.
* ``--serial N|N%`` — partition the fleet into rolling batches of that size;
  batches run sequentially so a bad rollout is caught before it reaches every
  host. ``0``/unset means one batch (bounded only by ``--forks``).
* ``--max-fail N|N%`` — once cumulative failures reach this threshold, no *new*
  batch starts; in-flight hosts finish, every not-yet-started host is marked
  ``skipped``. ``0`` (default) means the first failure stops new batches.

The summary taxonomy is ``changed / unchanged / failed / skipped`` per host, with
``ok = changed + unchanged`` as the umbrella for "ran and did not fail".
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

# Per-host terminal states. "ok" is not stored on a host (it is changed-or-
# unchanged); it exists only as a roll-up total in the summary.
STATUS_CHANGED = "changed"
STATUS_UNCHANGED = "unchanged"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


@dataclass
class HostOutcome:
    """Result of running one host's steps, in fleet-summary terms."""

    host: str
    status: str
    rc: int = 0
    changed_count: int = 0
    detail: dict | None = None


@dataclass
class FleetResult:
    outcomes: list[HostOutcome] = field(default_factory=list)
    aborted: bool = False

    @property
    def counts(self) -> dict[str, int]:
        c = {STATUS_CHANGED: 0, STATUS_UNCHANGED: 0, STATUS_FAILED: 0, STATUS_SKIPPED: 0}
        for outcome in self.outcomes:
            c[outcome.status] = c.get(outcome.status, 0) + 1
        return c

    @property
    def ok_count(self) -> int:
        c = self.counts
        return c[STATUS_CHANGED] + c[STATUS_UNCHANGED]

    @property
    def failed_count(self) -> int:
        return self.counts[STATUS_FAILED]

    @property
    def rc(self) -> int:
        return 1 if self.failed_count else 0


def _resolve_count(spec: str | int | None, total: int, *, default: int) -> int:
    """Turn an ``N`` / ``N%`` / ``None`` spec into an absolute host count.

    Percentages round *up* (ceil) so ``--serial 50%`` of 3 hosts is 2, not 1 —
    a rolling batch should never silently shrink to a trickle. ``default`` is
    returned for ``None``/empty.
    """
    if spec is None or spec == "":
        return default
    if isinstance(spec, int):
        return spec
    text = str(spec).strip()
    if text.endswith("%"):
        pct = float(text[:-1])
        return max(1, -(-int(pct) * total // 100)) if total else 0
    return int(text)


def parse_serial(spec: str | int | None, total: int) -> int:
    """Batch size for ``--serial``. ``0``/unset => one batch of every host."""
    size = _resolve_count(spec, total, default=0)
    if size <= 0:
        return total
    return min(size, total)


def parse_max_fail(spec: str | int | None, total: int) -> int:
    """Failure threshold for ``--max-fail``. Default 0 => first failure stops."""
    return _resolve_count(spec, total, default=0)


def partition_batches(hosts: list[str], serial: int) -> list[list[str]]:
    if serial <= 0:
        return [list(hosts)] if hosts else []
    return [hosts[i:i + serial] for i in range(0, len(hosts), serial)]


def run_fleet(
    hosts: list[str],
    runner: Callable[[str], HostOutcome],
    *,
    forks: int = 5,
    serial: str | int | None = None,
    max_fail: str | int | None = None,
) -> FleetResult:
    """Execute ``runner`` over ``hosts`` in rolling batches with a fail cap.

    ``runner`` is called once per host and must return a :class:`HostOutcome`;
    any exception it raises is caught and recorded as a ``failed`` host so one
    crashing host never takes down the scheduler. Once cumulative failures reach
    the ``max_fail`` threshold, remaining un-started hosts are marked
    ``skipped`` and no further batch begins.
    """
    result = FleetResult()
    if not hosts:
        return result

    serial_size = parse_serial(serial, len(hosts))
    threshold = parse_max_fail(max_fail, len(hosts))
    batches = partition_batches(hosts, serial_size)
    failures = 0
    workers = max(1, forks)

    for batch_index, batch in enumerate(batches):
        if _threshold_breached(failures, threshold):
            result.aborted = True
            for host in (h for b in batches[batch_index:] for h in b):
                result.outcomes.append(HostOutcome(host=host, status=STATUS_SKIPPED, rc=-1))
            break

        batch_outcomes = _run_batch(batch, runner, workers)
        for host in batch:
            result.outcomes.append(batch_outcomes[host])
            if batch_outcomes[host].status == STATUS_FAILED:
                failures += 1

    return result


def _threshold_breached(failures: int, threshold: int) -> bool:
    # Default threshold 0 means "stop new batches after the first failure".
    if threshold <= 0:
        return failures >= 1
    return failures >= threshold


def _run_batch(batch: list[str], runner: Callable[[str], HostOutcome], workers: int) -> dict[str, HostOutcome]:
    outcomes: dict[str, HostOutcome] = {}
    pool_size = min(workers, len(batch))
    with ThreadPoolExecutor(max_workers=pool_size) as executor:
        futures = {executor.submit(_safe_run, runner, host): host for host in batch}
        for future in futures:
            host = futures[future]
            outcomes[host] = future.result()
    return outcomes


def _safe_run(runner: Callable[[str], HostOutcome], host: str) -> HostOutcome:
    try:
        return runner(host)
    except Exception as exc:  # a crashing runner must not sink the whole fleet
        return HostOutcome(host=host, status=STATUS_FAILED, rc=1, detail={"error": str(exc)})


def classify(rc: int, changed_count: int) -> str:
    """Map a host's exit code + change count to a fleet status."""
    if rc != 0:
        return STATUS_FAILED
    return STATUS_CHANGED if changed_count > 0 else STATUS_UNCHANGED


def render_summary(result: FleetResult) -> str:
    """Render the per-host status table + totals line."""
    width = max((len(o.host) for o in result.outcomes), default=4)
    lines = ["Fleet summary:"]
    for outcome in result.outcomes:
        detail = ""
        if outcome.status in (STATUS_CHANGED, STATUS_UNCHANGED):
            detail = f" ({outcome.changed_count} changed)"
        elif outcome.status == STATUS_FAILED:
            detail = f" (rc={outcome.rc})"
        lines.append(f"  {outcome.host.ljust(width)}  {outcome.status}{detail}")
    c = result.counts
    lines.append(
        f"  totals: ok={result.ok_count} "
        f"changed={c[STATUS_CHANGED]} unchanged={c[STATUS_UNCHANGED]} "
        f"failed={c[STATUS_FAILED]} skipped={c[STATUS_SKIPPED]}"
    )
    if result.aborted:
        lines.append("  aborted: failure threshold reached; remaining hosts skipped")
    return "\n".join(lines)
