from __future__ import annotations

import threading
import time

from local81.fleet import (
    HostOutcome,
    classify,
    parse_max_fail,
    parse_serial,
    partition_batches,
    render_summary,
    run_fleet,
)


def _ok(host: str) -> HostOutcome:
    return HostOutcome(host=host, status="unchanged", rc=0)


def test_parse_serial_absolute_and_percent() -> None:
    assert parse_serial(None, 10) == 10  # unset => one batch of all
    assert parse_serial(0, 10) == 10
    assert parse_serial(3, 10) == 3
    assert parse_serial("3", 10) == 3
    assert parse_serial("50%", 10) == 5
    # percent rounds up so a rolling batch never silently shrinks to a trickle
    assert parse_serial("50%", 3) == 2
    assert parse_serial(99, 10) == 10  # clamped to fleet size


def test_parse_max_fail_default_and_percent() -> None:
    assert parse_max_fail(None, 10) == 0
    assert parse_max_fail(2, 10) == 2
    assert parse_max_fail("20%", 10) == 2


def test_partition_batches() -> None:
    assert partition_batches(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]
    assert partition_batches(["a", "b"], 0) == [["a", "b"]]
    assert partition_batches([], 2) == []


def test_classify_taxonomy() -> None:
    assert classify(0, 0) == "unchanged"
    assert classify(0, 3) == "changed"
    assert classify(1, 0) == "failed"


def test_run_fleet_all_ok() -> None:
    hosts = ["h1", "h2", "h3"]
    result = run_fleet(hosts, _ok, forks=3)
    assert result.rc == 0
    assert result.ok_count == 3
    assert result.failed_count == 0
    assert not result.aborted


def test_run_fleet_max_fail_stops_before_next_batch() -> None:
    # The chaos scenario: 10 hosts, --serial 3, host in batch 1 fails, --max-fail
    # 1 => no batch after the one that breached. Batch 1 = h0..h2 (h1 rigged to
    # fail). Threshold 1 reached after batch 1, so batches 2+ never start.
    hosts = [f"h{i}" for i in range(10)]

    def runner(host: str) -> HostOutcome:
        if host == "h1":
            return HostOutcome(host=host, status="failed", rc=1)
        return HostOutcome(host=host, status="unchanged", rc=0)

    result = run_fleet(hosts, runner, forks=3, serial=3, max_fail=1)

    assert result.aborted
    statuses = {o.host: o.status for o in result.outcomes}
    # Batch 1 ran fully:
    assert statuses["h0"] == "unchanged"
    assert statuses["h1"] == "failed"
    assert statuses["h2"] == "unchanged"
    # Everything from batch 2 on is skipped (h3..h9):
    for i in range(3, 10):
        assert statuses[f"h{i}"] == "skipped"
    c = result.counts
    assert c["failed"] == 1
    assert c["skipped"] == 7
    assert c["unchanged"] == 2
    assert result.rc == 1


def test_run_fleet_higher_threshold_continues() -> None:
    hosts = [f"h{i}" for i in range(6)]

    def runner(host: str) -> HostOutcome:
        if host in {"h1", "h4"}:
            return HostOutcome(host=host, status="failed", rc=1)
        return HostOutcome(host=host, status="changed", rc=0, changed_count=1)

    # serial 2 => batches [h0,h1][h2,h3][h4,h5]. Threshold 3 never reached
    # (only 2 failures), so all batches run; nothing skipped.
    result = run_fleet(hosts, runner, forks=2, serial=2, max_fail=3)
    assert not result.aborted
    assert result.counts["skipped"] == 0
    assert result.counts["failed"] == 2
    assert result.counts["changed"] == 4


def test_run_fleet_runner_exception_is_failed_not_crash() -> None:
    def runner(host: str) -> HostOutcome:
        if host == "boom":
            raise RuntimeError("connector exploded")
        return HostOutcome(host=host, status="unchanged", rc=0)

    result = run_fleet(["a", "boom", "c"], runner, forks=3, max_fail=5)
    statuses = {o.host: o.status for o in result.outcomes}
    assert statuses["boom"] == "failed"
    assert statuses["a"] == "unchanged"
    assert statuses["c"] == "unchanged"


def test_run_fleet_forks_bounds_concurrency() -> None:
    # With forks=2, no more than 2 runners should ever be in flight at once.
    live = 0
    peak = 0
    lock = threading.Lock()

    def runner(host: str) -> HostOutcome:
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep(0.02)
        with lock:
            live -= 1
        return HostOutcome(host=host, status="unchanged", rc=0)

    hosts = [f"h{i}" for i in range(6)]
    run_fleet(hosts, runner, forks=2, max_fail=10)
    assert peak <= 2


def test_render_summary_contains_taxonomy_and_abort_note() -> None:
    result = run_fleet(
        [f"h{i}" for i in range(4)],
        lambda host: HostOutcome(host=host, status="failed", rc=1),
        forks=4,
        serial=2,
        max_fail=1,
    )
    text = render_summary(result)
    assert "Fleet summary:" in text
    assert "totals:" in text
    assert "failed=" in text
    assert "skipped=" in text
    assert "aborted" in text
