from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from local26.config import load_config, resolve_config_path
from local26.state import load_scope_state


LOCAL26_VERSION = "0.1"
SCHEMA = "local26.plan.v0.1"


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _config_fingerprint(config_path: Path) -> str:
    return "sha256:" + hashlib.sha256(config_path.read_bytes()).hexdigest()


def _discover_files(source_dir: Path, since: str | None) -> tuple[list[Path], list[Path]]:
    all_files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    if since is None:
        return all_files, all_files
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        selected = [p for p in all_files if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) > since_dt]
    except Exception:
        selected = all_files
    return all_files, selected


def _git_checkout(repo_url: str, ref: str, scope_name: str, source_subdir: str) -> tuple[str, Path]:
    commit_sha = subprocess.check_output(["git", "-C", repo_url, "rev-parse", ref], text=True).strip()
    checkout_root = Path(".local26") / "workspaces" / scope_name / "checkouts" / commit_sha
    if not checkout_root.exists():
        checkout_root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", repo_url, str(checkout_root)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(checkout_root), "checkout", commit_sha], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    workspace_dir = checkout_root / source_subdir if source_subdir else checkout_root
    return commit_sha, workspace_dir


def _build_scope(scope, cfg, config_path: Path, only_scope: str | None = None) -> dict | None:
    if only_scope and scope.name != only_scope:
        return None
    if not scope.enabled:
        return None

    state = load_scope_state(scope.name)
    since = state.get("last_success")

    source_dir = scope.source_dir
    extra_inputs = {}
    section = f'scope "{scope.name}"'
    raw = config_path.read_text(encoding='utf-8')
    workspace_provider = None
    repo_url = ref = source_subdir = None
    if f'[{section}]' in raw:
        import configparser
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(raw)
        if parser.has_section(section):
            workspace_provider = parser.get(section, 'workspace', fallback=None)
            repo_url = parser.get(section, 'repo_url', fallback=None)
            ref = parser.get(section, 'ref', fallback='HEAD')
            source_subdir = parser.get(section, 'source_subdir', fallback='')
    if workspace_provider == 'git' and repo_url:
        commit_sha, workspace_dir = _git_checkout(repo_url, ref or 'HEAD', scope.name, source_subdir or '')
        source_dir = workspace_dir
        extra_inputs = {
            'workspace_provider': 'git',
            'commit_sha': commit_sha,
            'workspace_dir': str(workspace_dir.resolve()),
        }

    all_files, selected_files = _discover_files(source_dir, since)
    servers = scope.servers
    steps = []
    step_n = 1
    mkdir_steps = 0
    rsync_steps = 0
    rollbackable_steps = 0

    for server in servers:
        remote_dirs = sorted({str((scope.target_dir / f.relative_to(source_dir)).parent) for f in selected_files})
        if cfg.default_remote_mkdir:
            for remote_dir in remote_dirs:
                sid = f"scope:{scope.name}:{step_n:04d}"
                cmd = f'ssh "{server}" "mkdir -p -- \\\"{remote_dir}\\\""'
                steps.append({
                    'id': sid,
                    'type': 'mkdir',
                    'host': server,
                    'cmd': cmd,
                    'rollback': None,
                    'checks': {'requires': ['ssh']},
                })
                step_n += 1
                mkdir_steps += 1

        for file_path in selected_files:
            rel = file_path.relative_to(source_dir)
            remote_path = scope.target_dir / rel
            sid = f"scope:{scope.name}:{step_n:04d}"
            cmd = f'rsync {scope.rsync_opts} '
            rollback = None
            if scope.backup:
                cmd += f'--backup --suffix={scope.backup_suffix} '
                rollback = {
                    'type': 'restore',
                    'cmd': f'ssh "{server}" "cp -a -- \\\"{remote_path}{scope.backup_suffix}\\\" \\\"{remote_path}\\\""',
                }
                rollbackable_steps += 1
            cmd += f'-- "{file_path}" "{server}:{remote_path}"'
            steps.append({
                'id': sid,
                'type': 'rsync',
                'host': server,
                'cmd': cmd,
                'local_path': str(file_path),
                'remote_path': str(remote_path),
                'rollback': rollback,
                'checks': {'requires': ['ssh', 'rsync']},
            })
            step_n += 1
            rsync_steps += 1

    return {
        'scope': scope.name,
        'inputs': {
            'source_dir': str(scope.source_dir),
            'target_dir': str(scope.target_dir),
            'servers': servers,
            'rsync_opts': scope.rsync_opts,
            'backup': bool(scope.backup),
            'backup_suffix': scope.backup_suffix,
            'remote_mkdir': bool(cfg.default_remote_mkdir),
            **extra_inputs,
        },
        'discovery': {
            'strategy': scope.discovery,
            'since': since,
            'files_found': len(all_files),
            'files_selected': len(selected_files),
        },
        'routing': {
            'env_from_filename_prefix': cfg.routing_env_from_filename_prefix,
            'env_from_server_name_char_at': cfg.routing_env_from_server_name_char_at,
            'env_from_server_name_char_map': cfg.routing_env_from_server_name_char_map,
        },
        'steps': steps,
        'summary': {
            'counts': {
                'mkdir_steps': mkdir_steps,
                'rsync_steps': rsync_steps,
                'rollbackable_steps': rollbackable_steps,
                'warnings': [],
            }
        },
    }


def _render_summary(plan: dict, plan_path: Path) -> str:
    del plan_path
    lines: list[str] = []
    for scope in plan['scopes']:
        for step in scope.get('steps', []):
            timeout = step.get('timeout')
            timeout_text = '-' if timeout is None else str(timeout)
            lines.append(f"{step.get('id', '?')} | {step.get('type', 'step')} | {timeout_text} | pending")
    return '\n'.join(lines)


def run_plan(*, only_scope: str | None = None, output_format: str = 'json', print_stdout: bool = False, ci_mode: bool = False, summary: bool = False) -> int:
    if output_format != 'json':
        raise SystemExit(2)

    config_path = resolve_config_path()
    cfg = load_config(config_path)
    plan_id = f"{_now_compact()}-{_config_fingerprint(config_path).split(':', 1)[1][:8]}"
    plan = {
        'local26_version': LOCAL26_VERSION,
        'kind': 'plan',
        'mode': 'deploy',
        'schema': SCHEMA,
        'plan_id': plan_id,
        'created_at': _now_iso(),
        'config_fingerprint': _config_fingerprint(config_path),
        'scopes': [],
    }

    for scope in cfg.scopes:
        built = _build_scope(scope, cfg, config_path, only_scope)
        if built:
            plan['scopes'].append(built)

    plans_dir = Path('.local26/plans')
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f'{plan_id}.plan.json'
    if not ci_mode:
        plan_path.write_text(json.dumps(plan, separators=(',', ':')), encoding='utf-8')

    if summary:
        print(_render_summary(plan, plan_path))
        return 0

    payload = json.dumps(plan, separators=(',', ':'))
    if print_stdout or ci_mode:
        print(payload)
    else:
        print(plan_id)
    return 0
