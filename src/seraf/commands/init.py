from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class LegacyScope:
    name: str
    values: dict[str, str]


def _warn(message: str) -> None:
    print(f"seraf: warning: {message}", file=sys.stderr)


def _err(message: str) -> None:
    print(f"seraf: {message}", file=sys.stderr)


def _parse_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _normalize_servers(raw: str) -> str:
    tokens = raw.replace(",", " ").split()
    return ",".join(tokens)


def _parse_legacy(path: Path) -> list[LegacyScope]:
    scopes: OrderedDict[str, dict[str, str]] = OrderedDict()
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            name = stripped[1:-1].strip()
            if name not in scopes:
                scopes[name] = {}
            current = name
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in scopes[current]:
            scopes[current][key] = value
    return [LegacyScope(name=name, values=values) for name, values in scopes.items()]


def _state_timestamp(path: Path) -> str | None:
    if not path.exists():
        return None
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_init(*, import_path: str | None = None, force: bool = False, project: str | None = None) -> int:
    seraf_dir = Path('.seraf')
    config_path = seraf_dir / 'config.ini'
    state_dir = seraf_dir / 'state'
    plans_dir = seraf_dir / 'plans'
    runs_dir = seraf_dir / 'runs'
    logs_dir = seraf_dir / 'logs'

    if config_path.exists() and not force:
        _err(f"{config_path} already exists; rerun with --force")
        return 1

    legacy = Path(import_path) if import_path else Path('./settings.cfg')
    if import_path is None and not legacy.exists():
        _err('no legacy config provided and ./settings.cfg not found')
        return 1
    if not legacy.exists():
        _err(f'legacy config not found: {legacy}')
        return 1

    scopes = _parse_legacy(legacy)
    if not scopes:
        _err(f'no scopes found in legacy config: {legacy}')
        return 1

    seraf_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    valid_scopes: list[LegacyScope] = []
    for scope in scopes:
        values = scope.values
        required = ['source_dir', 'target_dir', 'servers']
        if any(key not in values for key in required):
            _err(f'legacy section [{scope.name}] missing required keys (source_dir, target_dir, servers)')
            return 1
        normalized = {
            'source_dir': values['source_dir'].strip(),
            'target_dir': values['target_dir'].strip(),
            'servers': _normalize_servers(values['servers']),
        }
        if 'rsync_opts' in values:
            normalized['rsync_opts'] = values['rsync_opts'].strip()
        if 'backup' in values:
            parsed = _parse_bool(values['backup'])
            if parsed is None:
                _warn(f"legacy section [{scope.name}] has invalid backup value '{values['backup']}'; expected true/false, ignoring")
            else:
                normalized['backup'] = 'true' if parsed else 'false'
        if 'backup_suffix' in values:
            normalized['backup_suffix'] = values['backup_suffix'].strip()
        valid_scopes.append(LegacyScope(scope.name, normalized))

    default_scope = valid_scopes[0].name
    project_name = project or Path.cwd().name

    config_lines = [
        '[seraf]',
        'version = 0.1',
        f'project = {project_name}',
        f'default_scope = {default_scope}',
        'state_dir = .seraf/state',
        'plans_dir = .seraf/plans',
        'runs_dir = .seraf/runs',
        'logs_dir = .seraf/logs',
        'lock_file = .seraf/seraf.lock',
        'require_plan_for_deploy = true',
        'fail_fast = true',
        'max_parallel = 4',
        'shell = /usr/bin/bash',
        '',
        '[tools]',
        'ssh = /usr/bin/ssh',
        'rsync = /usr/bin/rsync',
        'find = /usr/bin/find',
        '',
        '[defaults]',
        'rsync_opts = -az',
        'backup = true',
        'backup_suffix = .bkp',
        'remote_mkdir = true',
        'dry_run_default = false',
        'log_hosts = ',
        'log_dest_dir = .seraf/pulled-logs',
        'jboss_log_path = ',
        'apache_log_path = ',
        'engin_log_path = ',
        'smartxfr_log_path = ',
        '',
        '[routing]',
        'env_from_filename_prefix = s:sys,q:qa,p:production',
        'env_from_server_name_char_at = 4',
        'env_from_server_name_char_map = s:sys,q:qa,p:production',
        '',
    ]

    for scope in valid_scopes:
        config_lines.append(f'[scope "{scope.name}"]')
        config_lines.append('enabled = true')
        config_lines.append(f"source_dir = {scope.values['source_dir']}")
        config_lines.append(f"target_dir = {scope.values['target_dir']}")
        config_lines.append(f"servers = {scope.values['servers']}")
        config_lines.append('discovery = mtime_since_last_success')
        if 'rsync_opts' in scope.values:
            config_lines.append(f"rsync_opts = {scope.values['rsync_opts']}")
        if 'backup' in scope.values:
            config_lines.append(f"backup = {scope.values['backup']}")
        if 'backup_suffix' in scope.values:
            config_lines.append(f"backup_suffix = {scope.values['backup_suffix']}")
        config_lines.append('')

        last_path = Path('state') / f'{scope.name}.last'
        state = {
            'schema': 'seraf.state.v0.1',
            'scope': scope.name,
            'last_success': _state_timestamp(last_path),
            'last_plan_id': None,
            'last_run_id': None,
            'files_last_deployed_count': 0,
        }
        (state_dir / f'{scope.name}.json').write_text(json.dumps(state, separators=(',', ':')), encoding='utf-8')

    config_path.write_text('\n'.join(config_lines) + '\n', encoding='utf-8')
    return 0
