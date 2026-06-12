from __future__ import annotations

from pathlib import Path

from local81.commands.gc import RunDir, run_gc, select_runs_to_prune


def _runs(*mtimes: float) -> list[RunDir]:
    return [RunDir(path=Path(f"r{i}"), mtime=m) for i, m in enumerate(mtimes)]


def test_both_bounds_none_prunes_nothing() -> None:
    runs = _runs(1.0, 2.0, 3.0)
    assert select_runs_to_prune(runs, keep=None, max_age_days=None, now=100.0) == []


def test_keep_newest_n() -> None:
    runs = _runs(10.0, 20.0, 30.0, 40.0)
    doomed = select_runs_to_prune(runs, keep=2, max_age_days=None, now=100.0)
    # Newest two (40, 30) survive; 20 and 10 are doomed.
    assert sorted(r.mtime for r in doomed) == [10.0, 20.0]


def test_keep_larger_than_count_prunes_nothing() -> None:
    runs = _runs(10.0, 20.0)
    assert select_runs_to_prune(runs, keep=5, max_age_days=None, now=100.0) == []


def test_max_age_drops_old_runs() -> None:
    now = 10 * 86400.0
    # cutoff at 7 days => anything with mtime < 3*86400 is too old
    runs = _runs(2 * 86400.0, 5 * 86400.0, 9 * 86400.0)
    doomed = select_runs_to_prune(runs, keep=None, max_age_days=7, now=now)
    assert [r.mtime for r in doomed] == [2 * 86400.0]


def test_age_boundary_is_strict() -> None:
    now = 10 * 86400.0
    cutoff_mtime = now - 7 * 86400.0
    # exactly at cutoff survives (not < cutoff); one second older is doomed
    runs = _runs(cutoff_mtime, cutoff_mtime - 1)
    doomed = select_runs_to_prune(runs, keep=None, max_age_days=7, now=now)
    assert [r.mtime for r in doomed] == [cutoff_mtime - 1]


def test_keep_and_age_union() -> None:
    now = 100 * 86400.0
    runs = _runs(10 * 86400.0, 20 * 86400.0, 99 * 86400.0)
    # keep=1 dooms the two oldest; age=7 also dooms the two oldest -> union
    doomed = select_runs_to_prune(runs, keep=1, max_age_days=7, now=now)
    assert sorted(r.mtime for r in doomed) == [10 * 86400.0, 20 * 86400.0]


def _make_run_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "run.json").write_text("{}", encoding="utf-8")
    return d


def test_run_gc_no_policy_is_noop(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    _make_run_dir(runs_dir, "a")
    rc = run_gc(runs_dir=str(runs_dir))
    assert rc == 0
    assert "Nothing to do" in capsys.readouterr().out
    assert (runs_dir / "a").is_dir()


def test_run_gc_dry_run_deletes_nothing(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    for name in ("a", "b", "c"):
        _make_run_dir(runs_dir, name)
    rc = run_gc(keep=1, runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert "would remove" in out
    assert "Dry run" in out
    # all directories still present
    assert {p.name for p in runs_dir.iterdir()} == {"a", "b", "c"}


def test_run_gc_execute_removes_old(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    dirs = {name: _make_run_dir(runs_dir, name) for name in ("a", "b", "c")}
    # Make a oldest, c newest.
    import os
    os.utime(dirs["a"], (1.0, 1.0))
    os.utime(dirs["b"], (2.0, 2.0))
    os.utime(dirs["c"], (3.0, 3.0))
    rc = run_gc(keep=1, execute=True, runs_dir=str(runs_dir))
    out = capsys.readouterr().out
    assert rc == 0
    assert "removed" in out
    surviving = {p.name for p in runs_dir.iterdir()}
    assert surviving == {"c"}


def test_run_gc_missing_dir_is_noop(tmp_path, capsys) -> None:
    rc = run_gc(keep=1, runs_dir=str(tmp_path / "nope"))
    assert rc == 0
    assert "Nothing to remove" in capsys.readouterr().out
