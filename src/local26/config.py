from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ScopeConfig
from .profiles import load_profile_data, merge_profile

DEFAULT_CONFIG_PATH = Path(".local26/config.ini")
ALT_CONFIG_PATHS = (Path(".local26/config.yaml"), Path(".local26/config.yml"))
LEGACY_CONFIG_PATH = Path(".seraf/config.ini")
LEGACY_ALT_CONFIG_PATHS = (Path(".seraf/config.yaml"), Path(".seraf/config.yml"))
_SCOPE_SECTION_RE = re.compile(r'^scope "([^"]+)"$')


@dataclass(slots=True)
class ConfigValidationFinding:
    level: str
    name: str
    detail: str

    def render(self) -> str:
        return f"[{self.level}] {self.name}: {self.detail}"


@dataclass(slots=True)
class Local26Config:
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


_INI_ALLOWED_KEYS = {
    "local26": {
        "version",
        "project",
        "default_scope",
        "state_dir",
        "plans_dir",
        "runs_dir",
        "logs_dir",
        "lock_file",
        "require_plan_for_deploy",
        "fail_fast",
        "max_parallel",
        "shell",
    },
    "seraf": {
        "version",
        "project",
        "default_scope",
        "state_dir",
        "plans_dir",
        "runs_dir",
        "logs_dir",
        "lock_file",
        "require_plan_for_deploy",
        "fail_fast",
        "max_parallel",
        "shell",
    },
    "tools": {"ssh", "rsync", "find", "jq"},
    "defaults": {
        "rsync_opts",
        "backup",
        "backup_suffix",
        "remote_mkdir",
        "dry_run_default",
        "log_hosts",
        "log_dest_dir",
        "jboss_log_path",
        "apache_log_path",
        "engin_log_path",
        "smartxfr_log_path",
    },
    "routing": {
        "env_from_filename_prefix",
        "env_from_server_name_char_at",
        "env_from_server_name_char_map",
    },
    "access": {
        "allowed_users",
        "allowed_groups",
        "denied_users",
        "deny_root",
        "allow_remote_cmd",
    },
    "notifications": {"notify_on_success"},
    "notification.telegram": {"enabled", "bot_token", "chat_id", "api_base"},
    "notification.email": {"enabled", "to", "sendmail_bin", "subject_prefix"},
}
_SCOPE_ALLOWED_KEYS = {
    "enabled",
    "source_dir",
    "target_dir",
    "servers",
    "discovery",
    "rsync_opts",
    "backup",
    "backup_suffix",
}
_LOCAL26_REQUIRED_KEYS = {
    "version",
    "project",
    "default_scope",
    "state_dir",
    "plans_dir",
    "runs_dir",
    "logs_dir",
    "lock_file",
    "require_plan_for_deploy",
    "fail_fast",
    "max_parallel",
    "shell",
}
_TOOLS_REQUIRED_KEYS = {"ssh", "rsync", "find"}
_DEFAULTS_REQUIRED_KEYS = {
    "rsync_opts",
    "backup",
    "backup_suffix",
    "remote_mkdir",
    "dry_run_default",
    "log_hosts",
    "log_dest_dir",
    "jboss_log_path",
    "apache_log_path",
    "engin_log_path",
    "smartxfr_log_path",
}
_ROUTING_REQUIRED_KEYS = {
    "env_from_filename_prefix",
    "env_from_server_name_char_at",
    "env_from_server_name_char_map",
}
_SCOPE_REQUIRED_KEYS = {"enabled", "source_dir", "target_dir", "servers", "discovery"}
_BOOLEAN_KEYS = {
    ("local26", "require_plan_for_deploy"),
    ("local26", "fail_fast"),
    ("seraf", "require_plan_for_deploy"),
    ("seraf", "fail_fast"),
    ("defaults", "backup"),
    ("defaults", "remote_mkdir"),
    ("defaults", "dry_run_default"),
    ("access", "deny_root"),
    ("access", "allow_remote_cmd"),
    ("notifications", "notify_on_success"),
    ("notification.telegram", "enabled"),
    ("notification.email", "enabled"),
}
_SCOPE_BOOLEAN_KEYS = {"enabled", "backup"}


def _validation_finding(level: str, detail: str) -> ConfigValidationFinding:
    return ConfigValidationFinding(level, "config:schema", detail)


def _missing_keys(parser: configparser.ConfigParser, section: str, required: set[str]) -> list[str]:
    if not parser.has_section(section):
        return sorted(required)
    present = set(parser.options(section))
    return sorted(required - present)


def _validate_bool(parser: configparser.ConfigParser, section: str, option: str, findings: list[ConfigValidationFinding]) -> None:
    if parser.has_section(section) and parser.has_option(section, option):
        try:
            parser.getboolean(section, option)
        except ValueError:
            findings.append(_validation_finding("FAIL", f"[{section}] {option} must be true or false"))


def _validate_int(parser: configparser.ConfigParser, section: str, option: str, *, minimum: int, findings: list[ConfigValidationFinding]) -> None:
    if not (parser.has_section(section) and parser.has_option(section, option)):
        return
    raw = parser.get(section, option)
    try:
        value = int(raw)
    except ValueError:
        findings.append(_validation_finding("FAIL", f"[{section}] {option} must be an integer"))
        return
    if value < minimum:
        findings.append(_validation_finding("FAIL", f"[{section}] {option} must be >= {minimum}"))


def _validate_non_empty(parser: configparser.ConfigParser, section: str, option: str, findings: list[ConfigValidationFinding]) -> None:
    if parser.has_section(section) and parser.has_option(section, option) and not parser.get(section, option).strip():
        findings.append(_validation_finding("FAIL", f"[{section}] {option} must not be empty"))


def _validate_ini_config(path: Path) -> list[ConfigValidationFinding]:
    findings: list[ConfigValidationFinding] = []
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        with path.open(encoding="utf-8") as handle:
            parser.read_file(handle)
    except configparser.Error as exc:
        return [_validation_finding("FAIL", f"could not parse {path}: {exc}")]
    except OSError as exc:
        return [_validation_finding("FAIL", f"could not read {path}: {exc}")]

    sections = parser.sections()
    core_section = "local26" if parser.has_section("local26") else "seraf" if parser.has_section("seraf") else None
    if core_section is None:
        findings.append(_validation_finding("FAIL", "missing required [local26] section"))
    elif core_section == "seraf":
        findings.append(_validation_finding("WARN", "legacy [seraf] section is accepted but should be migrated to [local26]"))

    scopes: list[str] = []
    for section in sections:
        scope_match = _SCOPE_SECTION_RE.match(section)
        if scope_match:
            scope_name = scope_match.group(1).strip()
            scopes.append(scope_name)
            if not scope_name:
                findings.append(_validation_finding("FAIL", "scope section name must not be empty"))
            unknown = sorted(set(parser.options(section)) - _SCOPE_ALLOWED_KEYS)
            for key in unknown:
                findings.append(_validation_finding("FAIL", f"unknown key [{section}] {key}"))
            missing = sorted(_SCOPE_REQUIRED_KEYS - set(parser.options(section)))
            for key in missing:
                findings.append(_validation_finding("FAIL", f"missing required key [{section}] {key}"))
            for key in _SCOPE_BOOLEAN_KEYS:
                _validate_bool(parser, section, key, findings)
            _validate_non_empty(parser, section, "source_dir", findings)
            _validate_non_empty(parser, section, "target_dir", findings)
            _validate_non_empty(parser, section, "servers", findings)
            if parser.has_option(section, "discovery") and parser.get(section, "discovery") != "mtime_since_last_success":
                findings.append(_validation_finding("FAIL", f"[{section}] discovery must be mtime_since_last_success"))
            continue

        if section not in _INI_ALLOWED_KEYS:
            findings.append(_validation_finding("FAIL", f"unknown section [{section}]"))
            continue
        unknown = sorted(set(parser.options(section)) - _INI_ALLOWED_KEYS[section])
        for key in unknown:
            findings.append(_validation_finding("FAIL", f"unknown key [{section}] {key}"))

    if core_section:
        for key in _missing_keys(parser, core_section, _LOCAL26_REQUIRED_KEYS):
            findings.append(_validation_finding("FAIL", f"missing required key [{core_section}] {key}"))
        version = parser.get(core_section, "version", fallback="")
        if version and version != "0.1":
            findings.append(_validation_finding("FAIL", f"[{core_section}] version must be 0.1"))
        for key in ("project", "default_scope", "state_dir", "plans_dir", "runs_dir", "logs_dir", "lock_file", "shell"):
            _validate_non_empty(parser, core_section, key, findings)
        for key in ("require_plan_for_deploy", "fail_fast"):
            _validate_bool(parser, core_section, key, findings)
        _validate_int(parser, core_section, "max_parallel", minimum=1, findings=findings)
        default_scope = parser.get(core_section, "default_scope", fallback="").strip()
        if default_scope and scopes and default_scope not in scopes:
            findings.append(_validation_finding("FAIL", f"[{core_section}] default_scope {default_scope!r} does not match any scope"))

    for section, required in (("tools", _TOOLS_REQUIRED_KEYS), ("defaults", _DEFAULTS_REQUIRED_KEYS), ("routing", _ROUTING_REQUIRED_KEYS)):
        if not parser.has_section(section):
            findings.append(_validation_finding("FAIL", f"missing required [{section}] section"))
            continue
        for key in _missing_keys(parser, section, required):
            findings.append(_validation_finding("FAIL", f"missing required key [{section}] {key}"))

    for section, option in _BOOLEAN_KEYS:
        _validate_bool(parser, section, option, findings)
    _validate_int(parser, "routing", "env_from_server_name_char_at", minimum=1, findings=findings)

    if not scopes:
        findings.append(_validation_finding("WARN", "no [scope \"NAME\"] sections configured"))
    if not parser.has_section("access"):
        findings.append(_validation_finding("WARN", "no [access] section configured"))

    if not [finding for finding in findings if finding.level == "FAIL"]:
        findings.append(ConfigValidationFinding("PASS", "config:schema", f"{path} matches schema"))
    return findings


def _expect_mapping(value: Any, name: str, findings: list[ConfigValidationFinding]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        findings.append(_validation_finding("FAIL", f"{name} must be a mapping"))
        return {}
    return value


def _validate_yaml_config(path: Path) -> list[ConfigValidationFinding]:
    findings: list[ConfigValidationFinding] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [_validation_finding("FAIL", f"could not parse {path}: {exc}")]
    except OSError as exc:
        return [_validation_finding("FAIL", f"could not read {path}: {exc}")]
    data = _expect_mapping(data, "top-level config", findings)
    allowed_top = {"local26", "seraf", "tools", "defaults", "routing", "access", "notifications", "scopes"}
    for key in sorted(set(data) - allowed_top):
        findings.append(_validation_finding("FAIL", f"unknown top-level key {key!r}"))
    core = _expect_mapping(data.get("local26") or data.get("seraf"), "local26", findings)
    if not core:
        findings.append(_validation_finding("FAIL", "missing required local26 mapping"))
    elif core.get("version") != "0.1":
        findings.append(_validation_finding("FAIL", "local26.version must be 0.1"))
    scopes = _expect_mapping(data.get("scopes"), "scopes", findings)
    if not scopes:
        findings.append(_validation_finding("WARN", "no scopes configured"))
    default_scope = core.get("default_scope")
    if default_scope and scopes and default_scope not in scopes:
        findings.append(_validation_finding("FAIL", f"local26.default_scope {default_scope!r} does not match any scope"))
    if not data.get("access"):
        findings.append(_validation_finding("WARN", "no access policy configured"))
    if not [finding for finding in findings if finding.level == "FAIL"]:
        findings.append(ConfigValidationFinding("PASS", "config:schema", f"{path} matches schema"))
    return findings


def validate_config(path: str | Path = DEFAULT_CONFIG_PATH) -> list[ConfigValidationFinding]:
    try:
        config_path = resolve_config_path(path)
    except FileNotFoundError as exc:
        return [ConfigValidationFinding("WARN", "config:schema", f"missing config: {exc}")]
    if config_path.suffix in {".yaml", ".yml"}:
        return _validate_yaml_config(config_path)
    return _validate_ini_config(config_path)


def _scope_name(section: str, parser: configparser.ConfigParser) -> str | None:
    if section.startswith('scope "') and section.endswith('"'):
        return section[len('scope "'):-1]
    if section in {"local26", "seraf", "defaults", "routing", "tools", "notifications", "notification.telegram", "notification.email"}:
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
        "local26": {
            "project": parser.get("local26", "project", fallback=parser.get("seraf", "project", fallback=path.parent.parent.name)),
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
                "subject_prefix": parser.get("notification.email", "subject_prefix", fallback="[Local-26]"),
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
        "local26": {
            "project": (data.get("local26") or data.get("seraf") or {}).get("project", path.parent.parent.name),
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


def load_config(path: str | Path = DEFAULT_CONFIG_PATH, *, profile: str | None = None) -> Local26Config:
    path = resolve_config_path(path)
    if path.suffix in {".yaml", ".yml"}:
        base = _base_dict_from_yaml(path)
    else:
        base = _base_dict_from_ini(path)
    if profile:
        base = merge_profile(base, load_profile_data(profile, root=path.parent.parent))
    defaults = base["defaults"]
    routing = base["routing"]
    return Local26Config(
        project=base["local26"].get("project", path.parent.parent.name),
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
