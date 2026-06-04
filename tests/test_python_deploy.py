from __future__ import annotations

import json
from pathlib import Path

from local81.commands.deploy import _resolve_plan_path, parse_hosts_file, run_check, run_deploy


def _write_plan(path: Path, *, cmd: str = 'printf ok', rollback: bool = False,
                host: str = "web1", scope_name: str = "web",
                extra: dict | None = None) -> None:
    step = {
        "id": f"scope:{scope_name}:0001",
        "type": "rsync",
        "host": host,
        "cmd": cmd,
    }
    if rollback:
        step["rollback"] = {"cmd": "printf rollback"}
    payload = {
        "schema": "local81.plan.v0.1",
        "kind": "plan",
        "mode": "deploy",
        "plan_id": "p1",
        "scopes": [{"scope": scope_name, "steps": [step]}],
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_multi_host_plan(path: Path, hosts: list[str]) -> None:
    steps = []
    for i, host in enumerate(hosts, 1):
        steps.append({
            "id": f"scope:web:{i:04d}",
            "type": "rsync",
            "host": host,
            "cmd": "printf ok",
        })
    payload = {
        "schema": "local81.plan.v0.1",
        "kind": "plan",
        "mode": "deploy",
        "plan_id": "multi1",
        "scopes": [{"scope": "web", "steps": steps}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_hosts_file(path: Path, hosts: list[tuple[str, str, str]]) -> None:
    lines = ["# host\tserver\talias\toptional_flag"]
    for ip, server, alias in hosts:
        lines.append(f"{ip}\t{server}\t{alias}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------

def test_resolve_latest_plan_path(tmp_path: Path) -> None:
    plans_dir = tmp_path / ".local81" / "plans"
    plans_dir.mkdir(parents=True)
    older = plans_dir / "20260430T010101Z-aaaa1111.plan.json"
    newer = plans_dir / "20260501T020202Z-bbbb2222.plan.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")

    assert _resolve_plan_path(use_latest=True, plans_dir=str(plans_dir)) == newer


def test_run_deploy_dry_run_writes_run_and_state(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)

    rc = run_deploy(plan=str(plan_path), scope="web", dry_run=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert "dry run" in out
    run_files = list((tmp_path / ".local81" / "runs").glob("*/run.json"))
    assert len(run_files) == 1
    run = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert run["dry_run"] is True
    assert run["steps"][0]["stdout"] == ""
    assert (run_files[0].parent / "run.log").exists()
    state = json.loads((tmp_path / ".local81" / "state" / "web.json").read_text(encoding="utf-8"))
    assert state["last_plan_id"] == "p1"
    assert state["files_last_deployed_count"] == 1


def test_run_deploy_failure_records_stderr(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, cmd='printf broken >&2; exit 7')

    rc = run_deploy(plan=str(plan_path), scope="web", dry_run=False, fail_fast=True)
    out = capsys.readouterr().out

    assert rc == 7
    assert "broken" in out
    run_files = list((tmp_path / ".local81" / "runs").glob("*/run.json"))
    run = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert run["rc"] == 7
    assert run["steps"][0]["stderr"] == "broken"
    assert not (tmp_path / ".local81" / "state" / "web.json").exists()


def test_run_deploy_missing_scope_is_friendly(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)

    rc = run_deploy(plan=str(plan_path), scope="api")
    out = capsys.readouterr().out

    assert rc == 1
    assert "did not find any matching scopes" in out


# ---------------------------------------------------------------------------
# Phase 2: --check mode
# ---------------------------------------------------------------------------

def test_check_valid_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)

    rc = run_check(plan=str(plan_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Check passed" in out
    assert "Scopes: 1" in out
    assert "Total steps: 1" in out


def test_check_warns_for_missing_config_fingerprint(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)

    rc = run_check(plan=str(plan_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "[warn] plan is missing config_fingerprint provenance metadata" in out


def test_check_warns_for_stale_config_fingerprint(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".local81"
    config_dir.mkdir()
    (config_dir / "config.ini").write_text(
        "[local81]\n"
        "version = 0.1\n"
        "project = test\n"
        "default_scope = web\n"
        "state_dir = .local81/state\n"
        "plans_dir = .local81/plans\n"
        "runs_dir = .local81/runs\n"
        "logs_dir = .local81/logs\n"
        "lock_file = .local81/local81.lock\n"
        "require_plan_for_deploy = true\n"
        "fail_fast = true\n"
        "max_parallel = 1\n"
        "shell = /usr/bin/bash\n"
        "\n"
        "[tools]\n"
        "ssh = /usr/bin/ssh\n"
        "rsync = /usr/bin/rsync\n"
        "find = /usr/bin/find\n"
        "\n"
        "[defaults]\n"
        "rsync_opts = -az\n"
        "backup = false\n"
        "backup_suffix = .bkp\n"
        "remote_mkdir = true\n"
        "dry_run_default = false\n"
        "log_hosts =\n"
        "log_dest_dir = .local81/pulled-logs\n"
        "jboss_log_path =\n"
        "apache_log_path =\n"
        "engin_log_path =\n"
        "smartxfr_log_path =\n"
        "\n"
        "[routing]\n"
        "env_from_filename_prefix = s:sys,q:qa,p:production\n"
        "env_from_server_name_char_at = 4\n"
        "env_from_server_name_char_map = s:sys,q:qa,p:production\n"
        "\n"
        "[access]\n"
        "allowed_users =\n"
        "allowed_groups =\n"
        "denied_users =\n"
        "deny_root = false\n"
        "allow_remote_cmd = false\n"
        "\n"
        "[scope \"web\"]\n"
        "enabled = true\n"
        "source_dir = /tmp/source\n"
        "target_dir = /srv/target\n"
        "servers = web1\n"
        "discovery = mtime_since_last_success\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, extra={
        "local81_version": "0.1",
        "created_at": "2026-01-01T00:00:00Z",
        "config_fingerprint": "sha256:" + ("0" * 64),
    })

    rc = run_check(plan=str(plan_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "[warn] plan config_fingerprint does not match current config .local81/config.ini" in out


def test_check_latest_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plans_dir = tmp_path / ".local81" / "plans"
    plans_dir.mkdir(parents=True)
    plan_path = plans_dir / "20260501T020202Z-p1.plan.json"
    _write_plan(plan_path)

    rc = run_check(use_latest=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert ".local81/plans/20260501T020202Z-p1.plan.json" in out


def test_check_missing_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = run_check(plan=str(tmp_path / "nope.json"))
    out = capsys.readouterr().out
    assert rc == 1
    assert "could not find" in out


def test_check_invalid_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all", encoding="utf-8")
    rc = run_check(plan=str(bad))
    out = capsys.readouterr().out
    assert rc == 1
    assert "not valid JSON" in out


def test_check_missing_keys(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"kind": "plan"}), encoding="utf-8")
    rc = run_check(plan=str(p))
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing required key" in out


def test_check_wrong_kind(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "wrong.json"
    p.write_text(json.dumps({
        "kind": "report", "mode": "deploy", "schema": "local81.plan.v0.1",
        "plan_id": "x", "scopes": [],
    }), encoding="utf-8")
    rc = run_check(plan=str(p))
    out = capsys.readouterr().out
    assert rc == 1
    assert "kind should be 'plan'" in out


def test_check_via_run_deploy(tmp_path: Path, monkeypatch, capsys) -> None:
    """--check flag passed through run_deploy."""
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)
    rc = run_deploy(plan=str(plan_path), check=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Check passed" in out


# ---------------------------------------------------------------------------
# Phase 2: hosts file parsing
# ---------------------------------------------------------------------------

def test_parse_hosts_file(tmp_path: Path) -> None:
    hf = tmp_path / "hosts.txt"
    _write_hosts_file(hf, [
        ("10.0.0.1", "server1", "s1"),
        ("10.0.0.2", "server2", "s2"),
    ])
    hosts = parse_hosts_file(str(hf))
    assert len(hosts) == 2
    assert hosts[0] == {"ip": "10.0.0.1", "server": "server1", "alias": "s1"}
    assert hosts[1] == {"ip": "10.0.0.2", "server": "server2", "alias": "s2"}


def test_parse_hosts_file_skips_comments(tmp_path: Path) -> None:
    hf = tmp_path / "hosts.txt"
    hf.write_text("# header\n10.0.0.1\tsvr1\ta1\n; comment\n10.0.0.2\tsvr2\ta2\n", encoding="utf-8")
    hosts = parse_hosts_file(str(hf))
    assert len(hosts) == 2


def test_parse_hosts_file_empty(tmp_path: Path) -> None:
    hf = tmp_path / "hosts.txt"
    hf.write_text("# only comments\n", encoding="utf-8")
    hosts = parse_hosts_file(str(hf))
    assert hosts == []


# ---------------------------------------------------------------------------
# Phase 2: integration tests (mocked, no network)
# ---------------------------------------------------------------------------

def test_deploy_dry_run_creates_run_record(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)
    rc = run_deploy(plan=str(plan_path), dry_run=True)
    assert rc == 0
    run_files = list((tmp_path / ".local81" / "runs").glob("*/run.json"))
    assert len(run_files) == 1
    data = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert data["dry_run"] is True
    assert data["rc"] == 0


def test_deploy_latest_plan_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plans_dir = tmp_path / ".local81" / "plans"
    plans_dir.mkdir(parents=True)
    older = plans_dir / "20260430T010101Z-old.plan.json"
    newer = plans_dir / "20260501T020202Z-new.plan.json"
    _write_plan(older, scope_name="old")
    _write_plan(newer, scope_name="web")

    rc = run_deploy(use_latest=True, dry_run=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert ".local81/plans/20260501T020202Z-new.plan.json" in out


def test_deploy_missing_plan_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = run_deploy(plan=str(tmp_path / "missing.json"))
    out = capsys.readouterr().out
    assert rc == 1
    assert "could not find" in out


def test_deploy_empty_hosts_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)
    hf = tmp_path / "empty_hosts.txt"
    hf.write_text("# nothing\n", encoding="utf-8")
    rc = run_deploy(plan=str(plan_path), hosts_file=str(hf))
    out = capsys.readouterr().out
    assert rc == 1
    assert "no hosts" in out


# ---------------------------------------------------------------------------
# Phase 3: multi-host deploy
# ---------------------------------------------------------------------------

def test_deploy_multi_host_sequential(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_multi_host_plan(plan_path, ["host1", "host2"])
    hf = tmp_path / "hosts.txt"
    _write_hosts_file(hf, [("10.0.0.1", "host1", "host1"), ("10.0.0.2", "host2", "host2")])

    rc = run_deploy(plan=str(plan_path), dry_run=True, hosts_file=str(hf))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Per-host results:" in out
    assert "host1: ok" in out
    assert "host2: ok" in out
    run_files = list((tmp_path / ".local81" / "runs").glob("*/run.json"))
    data = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert "hosts" in data
    assert len(data["hosts"]) == 2


def test_deploy_multi_host_parallel(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_multi_host_plan(plan_path, ["hostA", "hostB", "hostC"])
    hf = tmp_path / "hosts.txt"
    _write_hosts_file(hf, [
        ("10.0.0.1", "hostA", "hostA"),
        ("10.0.0.2", "hostB", "hostB"),
        ("10.0.0.3", "hostC", "hostC"),
    ])

    rc = run_deploy(plan=str(plan_path), dry_run=True, hosts_file=str(hf), parallel=True, max_parallel=3)
    out = capsys.readouterr().out

    assert rc == 0
    assert "Parallel: yes" in out
    assert "Per-host results:" in out


def test_deploy_remote_cmd_uses_ssh_target(tmp_path: Path, monkeypatch, capsys) -> None:
    import local81.commands.deploy as deploy_module

    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    payload = {
        "schema": "local81.plan.v0.1",
        "kind": "plan",
        "mode": "deploy",
        "plan_id": "remote1",
        "scopes": [{"scope": "web", "steps": [
            {"id": "scope:web:0001", "type": "remote_cmd", "server": "web1", "cmd": "systemctl status app"}
        ]}],
    }
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    captured: list[tuple[str, str]] = []

    def fake_run_remote(host: str, command: str, timeout_seconds=None, *, dry_run: bool = False):
        captured.append((host, command))
        return 0, "ok", "", False

    monkeypatch.setattr(deploy_module, "_run_remote", fake_run_remote)

    rc = run_deploy(plan=str(plan_path), dry_run=False)
    out = capsys.readouterr().out

    assert rc == 0
    assert "on web1" in out
    assert captured == [("web1", "systemctl status app")]
    run_files = list((tmp_path / ".local81" / "runs").glob("*/run.json"))
    run = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert run["steps"][0]["host"] == "web1"


def test_deploy_multi_host_fail_fast(tmp_path: Path, monkeypatch, capsys) -> None:
    """With fail-fast, a failing host should prevent subsequent hosts in sequential mode."""
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    # First host will fail, second should not run (sequential + fail-fast)
    steps = [
        {"id": "scope:web:0001", "type": "rsync", "host": "badhost",
         "cmd": "exit 1"},
        {"id": "scope:web:0002", "type": "rsync", "host": "goodhost",
         "cmd": "printf ok"},
    ]
    payload = {
        "schema": "local81.plan.v0.1", "kind": "plan", "mode": "deploy",
        "plan_id": "ff1",
        "scopes": [{"scope": "web", "steps": steps}],
    }
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    hf = tmp_path / "hosts.txt"
    _write_hosts_file(hf, [("10.0.0.1", "badhost", "badhost"), ("10.0.0.2", "goodhost", "goodhost")])

    rc = run_deploy(plan=str(plan_path), hosts_file=str(hf), fail_fast=True)
    out = capsys.readouterr().out

    assert rc != 0
    assert "FAILED" in out


def test_deploy_per_host_status_output(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "plan.json"
    _write_multi_host_plan(plan_path, ["alpha", "beta"])
    hf = tmp_path / "hosts.txt"
    _write_hosts_file(hf, [("10.0.0.1", "alpha", "alpha"), ("10.0.0.2", "beta", "beta")])

    rc = run_deploy(plan=str(plan_path), dry_run=True, hosts_file=str(hf))
    out = capsys.readouterr().out

    assert rc == 0
    assert "alpha" in out
    assert "beta" in out
    assert "Per-host results:" in out


# ---------------------------------------------------------------------------
# CLI parser tests
# ---------------------------------------------------------------------------

def test_cli_deploy_latest_flag() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["deploy", "--latest"])
    assert args.latest is True
    assert args.plan is None


def test_cli_deploy_check_flag() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["deploy", "--plan", "x.json", "--check"])
    assert args.check is True


def test_cli_deploy_hosts_file_flag() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["deploy", "--plan", "x.json", "--hosts-file", "hosts.txt"])
    assert args.hosts_file == "hosts.txt"


def test_cli_deploy_parallel_flag() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["deploy", "--plan", "x.json", "--parallel"])
    assert args.parallel is True


def test_cli_history_command() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["history"])
    assert args.command == "history"
    assert args.limit == 20


def test_cli_logs_command() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["logs", "run-123"])
    assert args.command == "logs"
    assert args.run_id == "run-123"


def test_cli_diff_command() -> None:
    from local81.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["diff", "a.json", "b.json"])
    assert args.command == "diff"
    assert args.plan_a == "a.json"
    assert args.plan_b == "b.json"
