from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ScopeConfig
from .profiles import load_profile_data, merge_profile

DEFAULT_CONFIG_PATH = Path(".local81/config.ini")
ALT_CONFIG_PATHS = (Path(".local81/config.yaml"), Path(".local81/config.yml"))
LEGACY_CONFIG_PATH = Path(".seraf/config.ini")
LEGACY_ALT_CONFIG_PATHS = (Path(".seraf/config.yaml"), Path(".seraf/config.yml"))


@dataclass(slots=True)
class Local81Config:
    project: str
    scopes: list[ScopeConfig] = field(default_factory=list)
    default_rsync_opts: str = "-az"
    default_backup: bool = True
    default_backup_suffix: str = ".bkp"
    default_remote_mkdir: bool = True
    routing_env_from_filename_prefix: str = "s:sys,q:qa,p:production"
    routing_env_from_server_name_char_at: int = 4
    routing_env_from_server_name_char_map: str = "s:sys,q:qa,p:production"
    profile: str | None = None
    notifications: dict[str, Any] = field(default_factory=dict)


def resolve_config_path(path: str | Path = DEFAULT_CONFIG_PATH) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    sibling_yaml = (candidate.with_suffix(".yaml"), candidate.with_suffix(".yml"))
    for alt in sibling_yaml:
        if alt.is_file():
            return alt
    if candidate == DEFAULT_CONFIG_PATH:
        for alt in ALT_CONFIG_PATHS:
            if alt.is_file():
                return alt
        if LEGACY_CONFIG_PATH.is_file():
            return LEGACY_CONFIG_PATH
        for alt in LEGACY_ALT_CONFIG_PATHS:
            if alt.is_file():
                return alt
    raise FileNotFoundError(candidate)


def _get_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool) -> bool:
    if parser.has_option(section, option):
        return parser.getboolean(section, option)
    return fallback


def _scope_name(section: str, parser: configparser.ConfigParser) -> str | None:
    if section.startswith('scope "') and section.endswith('"'):
        return section[len('scope "'):-1]
    if section in {"local81", "seraf", "defaults", "routing", "tools", "notifications", "notification.telegram", "notification.email"}:
        return None
    required_like_scope = {"source_dir", "target_dir", "servers"}
    if required_like_scope.issubset(set(parser.options(section))):
        return section
    return None


def _base_dict_from_ini(path: Path) -> dict[str, Any]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    scopes: dict[str, Any] = {}
    for section in parser.sections():
        name = _scope_name(section, parser)
        if not name:
            continue
        scopes[name] = {
            "enabled": _get_bool(parser, section, "enabled", True),
            "source_dir": parser.get(section, "source_dir", fallback="."),
            "target_dir": parser.get(section, "target_dir", fallback="."),
            "servers": [s for s in parser.get(section, "servers", fallback="").split(",") if s],
            "discovery": parser.get(section, "discovery", fallback="mtime_since_last_success"),
            "rsync_opts": parser.get(section, "rsync_opts", fallback=parser.get("defaults", "rsync_opts", fallback="-az")),
            "backup": _get_bool(parser, section, "backup", _get_bool(parser, "defaults", "backup", True)),
            "backup_suffix": parser.get(section, "backup_suffix", fallback=parser.get("defaults", "backup_suffix", fallback=".bkp")),
        }
    return {
        "local81": {
            "project": parser.get("local81", "project", fallback=parser.get("seraf", "project", fallback=path.parent.parent.name)),
        },
        "defaults": {
            "rsync_opts": parser.get("defaults", "rsync_opts", fallback="-az"),
            "backup": _get_bool(parser, "defaults", "backup", True),
            "backup_suffix": parser.get("defaults", "backup_suffix", fallback=".bkp"),
            "remote_mkdir": _get_bool(parser, "defaults", "remote_mkdir", True),
        },
        "routing": {
            "env_from_filename_prefix": parser.get("routing", "env_from_filename_prefix", fallback="s:sys,q:qa,p:production"),
            "env_from_server_name_char_at": parser.getint("routing", "env_from_server_name_char_at", fallback=4),
            "env_from_server_name_char_map": parser.get("routing", "env_from_server_name_char_map", fallback="s:sys,q:qa,p:production"),
        },
        "notifications": {
            "notify_on_success": _get_bool(parser, "notifications", "notify_on_success", False),
            "telegram": {
                "enabled": _get_bool(parser, "notification.telegram", "enabled", False),
                "bot_token": parser.get("notification.telegram", "bot_token", fallback=""),
                "chat_id": parser.get("notification.telegram", "chat_id", fallback=""),
                "api_base": parser.get("notification.telegram", "api_base", fallback="https://api.telegram.org"),
            },
            "email": {
                "enabled": _get_bool(parser, "notification.email", "enabled", False),
                "to": parser.get("notification.email", "to", fallback=""),
                "sendmail_bin": parser.get("notification.email", "sendmail_bin", fallback="sendmail"),
                "subject_prefix": parser.get("notification.email", "subject_prefix", fallback="[Local-81]"),
            },
        },
        "scopes": scopes,
    }


def _base_dict_from_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping at top level in {path}")
    defaults = data.get("defaults") or {}
    routing = data.get("routing") or {}
    notifications = data.get("notifications") or {}
    scopes = data.get("scopes") or {}
    return {
        "local81": {
            "project": (data.get("local81") or data.get("seraf") or {}).get("project", path.parent.parent.name),
        },
        "defaults": {
            "rsync_opts": defaults.get("rsync_opts", "-az"),
            "backup": bool(defaults.get("backup", True)),
            "backup_suffix": defaults.get("backup_suffix", ".bkp"),
            "remote_mkdir": bool(defaults.get("remote_mkdir", True)),
        },
        "routing": {
            "env_from_filename_prefix": routing.get("env_from_filename_prefix", "s:sys,q:qa,p:production"),
            "env_from_server_name_char_at": int(routing.get("env_from_server_name_char_at", 4)),
            "env_from_server_name_char_map": routing.get("env_from_server_name_char_map", "s:sys,q:qa,p:production"),
        },
        "notifications": notifications,
        "scopes": scopes,
    }


def _build_scope_configs(data: dict[str, Any], defaults: dict[str, Any]) -> list[ScopeConfig]:
    scopes: list[ScopeConfig] = []
    for name, values in (data.get("scopes") or {}).items():
        values = values or {}
        servers = values.get("servers", [])
        if isinstance(servers, str):
            servers = [s for s in servers.split(",") if s]
        scopes.append(
            ScopeConfig(
                name=name,
                enabled=bool(values.get("enabled", True)),
                source_dir=Path(values.get("source_dir", ".")),
                target_dir=Path(values.get("target_dir", ".")),
                servers=servers,
                discovery=values.get("discovery", "mtime_since_last_success"),
                rsync_opts=values.get("rsync_opts", defaults["rsync_opts"]),
                backup=values.get("backup", defaults["backup"]),
                backup_suffix=values.get("backup_suffix", defaults["backup_suffix"]),
            )
        )
    return scopes


def load_config(path: str | Path = DEFAULT_CONFIG_PATH, *, profile: str | None = None) -> Local81Config:
    path = resolve_config_path(path)
    if path.suffix in {".yaml", ".yml"}:
        base = _base_dict_from_yaml(path)
    else:
        base = _base_dict_from_ini(path)
    if profile:
        base = merge_profile(base, load_profile_data(profile, root=path.parent.parent))
    defaults = base["defaults"]
    routing = base["routing"]
    return Local81Config(
        project=base["local81"].get("project", path.parent.parent.name),
        scopes=_build_scope_configs(base, defaults),
        default_rsync_opts=defaults.get("rsync_opts", "-az"),
        default_backup=bool(defaults.get("backup", True)),
        default_backup_suffix=defaults.get("backup_suffix", ".bkp"),
        default_remote_mkdir=bool(defaults.get("remote_mkdir", True)),
        routing_env_from_filename_prefix=routing.get("env_from_filename_prefix", "s:sys,q:qa,p:production"),
        routing_env_from_server_name_char_at=int(routing.get("env_from_server_name_char_at", 4)),
        routing_env_from_server_name_char_map=routing.get("env_from_server_name_char_map", "s:sys,q:qa,p:production"),
        profile=profile,
        notifications=base.get("notifications", {}),
    )
