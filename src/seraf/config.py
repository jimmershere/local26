from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

from .models import ScopeConfig


@dataclass(slots=True)
class SerafConfig:
    project: str
    scopes: list[ScopeConfig] = field(default_factory=list)
    default_rsync_opts: str = "-az"
    default_backup: bool = True
    default_backup_suffix: str = ".bkp"
    default_remote_mkdir: bool = True
    routing_env_from_filename_prefix: str = "s:sys,q:qa,p:production"
    routing_env_from_server_name_char_at: int = 4
    routing_env_from_server_name_char_map: str = "s:sys,q:qa,p:production"


def _get_bool(parser: configparser.ConfigParser, section: str, option: str, fallback: bool) -> bool:
    if parser.has_option(section, option):
        return parser.getboolean(section, option)
    return fallback


def _scope_name(section: str, parser: configparser.ConfigParser) -> str | None:
    if section.startswith('scope "') and section.endswith('"'):
        return section[len('scope "'):-1]
    if section in {"seraf", "defaults", "routing", "tools"}:
        return None
    required_like_scope = {"source_dir", "target_dir", "servers"}
    if required_like_scope.issubset(set(parser.options(section))):
        return section
    return None


def load_config(path: str | Path = ".seraf/config.ini") -> SerafConfig:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    parser.read(path, encoding="utf-8")

    project = parser.get("seraf", "project", fallback=path.parent.parent.name)
    default_rsync_opts = parser.get("defaults", "rsync_opts", fallback="-az")
    default_backup = _get_bool(parser, "defaults", "backup", True)
    default_backup_suffix = parser.get("defaults", "backup_suffix", fallback=".bkp")
    default_remote_mkdir = _get_bool(parser, "defaults", "remote_mkdir", True)

    routing_prefix = parser.get("routing", "env_from_filename_prefix", fallback="s:sys,q:qa,p:production")
    routing_char_at = parser.getint("routing", "env_from_server_name_char_at", fallback=4)
    routing_char_map = parser.get("routing", "env_from_server_name_char_map", fallback="s:sys,q:qa,p:production")

    scopes: list[ScopeConfig] = []
    for section in parser.sections():
        name = _scope_name(section, parser)
        if not name:
            continue
        scopes.append(
            ScopeConfig(
                name=name,
                enabled=_get_bool(parser, section, "enabled", True),
                source_dir=Path(parser.get(section, "source_dir", fallback=".")),
                target_dir=Path(parser.get(section, "target_dir", fallback=".")),
                servers=[s for s in parser.get(section, "servers", fallback="").split(",") if s],
                discovery=parser.get(section, "discovery", fallback="mtime_since_last_success"),
                rsync_opts=parser.get(section, "rsync_opts", fallback=default_rsync_opts),
                backup=_get_bool(parser, section, "backup", default_backup),
                backup_suffix=parser.get(section, "backup_suffix", fallback=default_backup_suffix),
            )
        )

    return SerafConfig(
        project=project,
        scopes=scopes,
        default_rsync_opts=default_rsync_opts,
        default_backup=default_backup,
        default_backup_suffix=default_backup_suffix,
        default_remote_mkdir=default_remote_mkdir,
        routing_env_from_filename_prefix=routing_prefix,
        routing_env_from_server_name_char_at=routing_char_at,
        routing_env_from_server_name_char_map=routing_char_map,
    )
