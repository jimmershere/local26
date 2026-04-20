from __future__ import annotations

import json
import os
from pathlib import Path

from seraf.cli import build_parser
from seraf.commands.deploy import run_deploy
from seraf.commands.doctor import run_doctor
from seraf.commands.hooks import run_hooks
from seraf.commands.profiles import run_profile_create, run_profiles
from seraf.config import load_config


def _write_plan(path: Path, *, cmd: str = "printf ok", host: str = "web1") -> None:
    payload = {
        "schema": "seraf.plan.v0.1",
        "kind": "plan",
        "mode": "deploy",
        "plan_id": "p1",
        "scopes": [{"scope": "web", "steps": [{"id": "scope:web:0001", "type": "rsync", "host": host, "cmd": cmd}]}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[seraf]\n"
        "project = demo\n\n"
        "[defaults]\n"
        "rsync_opts = -az\n"
        "backup = true\n"
        "backup_suffix = .bkp\n"
        "remote_mkdir = true\n\n"
        "[routing]\n"
        "env_from_filename_prefix = s:sys\n"
        "env_from_server_name_char_at = 4\n"
        "env_from_server_name_char_map = s:sys\n\n"
        "[notifications]\n"
        "notify_on_success = false\n\n"
        "[notification.telegram]\n"
        "enabled = true\n"
        "bot_token = 123:abc\n"
        "chat_id = 42\n\n"
        "[scope \"web\"]\n"
        "enabled = true\n"
        "source_dir = ./src\n"
        "target_dir = /srv/app\n"
        "servers = web1\n"
        "discovery = mtime_since_last_success\n",
        encoding="utf-8",
    )


def test_run_hooks_lists_statuses(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    hooks_dir = tmp_path / ".seraf" / "hooks"
    hooks_dir.mkdir(parents=True)
    pre = hooks_dir / "pre-deploy.sh"
    pre.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    os.chmod(pre, 0o755)
    rc = run_hooks()
    out = capsys.readouterr().out
    assert rc == 0
    assert "pre-deploy.sh: installed" in out
    assert "post-deploy.sh: missing" in out


def test_pre_deploy_hook_abort(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    pre = tmp_path / ".seraf" / "hooks" / "pre-deploy.sh"
    pre.parent.mkdir(parents=True)
    pre.write_text("#!/usr/bin/env bash\necho nope\nexit 9\n", encoding="utf-8")
    os.chmod(pre, 0o755)
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    rc = run_deploy(plan=str(plan))
    out = capsys.readouterr().out
    assert rc == 9
    assert "Pre-deploy hook failed" in out


def test_post_deploy_hook_warns_only(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    post = tmp_path / ".seraf" / "hooks" / "post-deploy.sh"
    post.parent.mkdir(parents=True)
    post.write_text("#!/usr/bin/env bash\nexit 5\n", encoding="utf-8")
    os.chmod(post, 0o755)
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    rc = run_deploy(plan=str(plan), dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "post-deploy hook failed" in out


def test_profiles_create_and_list(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = run_profile_create("prod")
    assert rc == 0
    assert (tmp_path / ".seraf" / "profiles" / "prod.yaml").exists()
    rc = run_profiles()
    out = capsys.readouterr().out
    assert rc == 0
    assert "prod" in out


def test_profile_merge_changes_scope_and_notifications(tmp_path: Path) -> None:
    _write_config(tmp_path / ".seraf" / "config.ini")
    profile = tmp_path / ".seraf" / "profiles" / "prod.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        "defaults:\n  rsync_opts: -aP\nnotifications:\n  notify_on_success: true\nscopes:\n  web:\n    target_dir: /srv/prod\n    servers: [prod1, prod2]\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path / ".seraf" / "config.ini", profile="prod")
    assert cfg.default_rsync_opts == "-aP"
    assert cfg.notifications["notify_on_success"] is True
    assert str(cfg.scopes[0].target_dir) == "/srv/prod"
    assert cfg.scopes[0].servers == ["prod1", "prod2"]


def test_doctor_validates_profile(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    prof = tmp_path / ".seraf" / "profiles" / "prod.yaml"
    prof.parent.mkdir(parents=True)
    prof.write_text("scopes:\n  web:\n    target_dir: /srv/prod\n", encoding="utf-8")
    rc = run_doctor(profile="prod")
    out = capsys.readouterr().out
    assert rc in (0, 1)
    assert "config:profile" in out


def test_deploy_notifications_success_forced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    calls = []
    def fake_post_json(url, payload, timeout=10):
        calls.append((url, payload))
    monkeypatch.setattr("seraf.notifications.post_json", fake_post_json)
    rc = run_deploy(plan=str(plan), dry_run=True, notify=True)
    assert rc == 0
    assert calls
    assert calls[0][1]["chat_id"] == "42"
    assert "status=success" in calls[0][1]["text"]


def test_deploy_notifications_quiet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    calls = []
    monkeypatch.setattr("seraf.notifications.post_json", lambda *args, **kwargs: calls.append(args))
    rc = run_deploy(plan=str(plan), dry_run=True, notify=True, quiet=True)
    assert rc == 0
    assert calls == []


def test_timeout_alert_sends_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path / ".seraf" / "config.ini")
    plan = tmp_path / "plan.json"
    _write_plan(plan, cmd="python3 - <<'PY'\nimport time\ntime.sleep(0.2)\nPY")
    calls = []
    monkeypatch.setattr("seraf.notifications.post_json", lambda url, payload, timeout=10: calls.append(payload))
    rc = run_deploy(plan=str(plan), step_timeout=0, notify=True)
    assert rc == 124
    assert any("warning" in call["text"] for call in calls)


def test_cli_profile_and_commands() -> None:
    parser = build_parser()
    args = parser.parse_args(["--profile", "prod", "deploy", "--plan", "x.json", "--notify", "--quiet"])
    assert args.profile == "prod"
    assert args.notify is True
    assert args.quiet is True
    args = parser.parse_args(["profile", "create", "prod"])
    assert args.profile_command == "create"
