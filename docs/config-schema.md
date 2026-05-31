# LOCAL-26 Config Schema v0.1

This document defines the canonical `.local26/config.ini` contract for LOCAL-26 v0.1.

## Parsing and validation rules

LOCAL-26 config parsing is intentionally compatibility-oriented in v0.1:

- Keys are case-sensitive and should match the documented names.
- Access-policy booleans must be `true` or `false`; invalid values are reported as blocking policy findings.
- Paths should be non-empty strings.
- `scope` names should be non-empty and unique.
- `servers` should be a comma-separated list with no surrounding spaces per item.
- Unknown non-scope sections are ignored by the runtime unless a command explicitly documents support for them.

## Canonical structure

### `[local26]` (required)

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `version` | string | yes | `0.1` | Must equal `0.1` for this schema version. |
| `project` | string | yes | none | Human-readable project identifier. |
| `default_scope` | string | yes | none | Must match one defined scope name when scopes exist. |
| `state_dir` | path | yes | `.local26/state` | State JSON directory. |
| `plans_dir` | path | yes | `.local26/plans` | Plan artifacts directory. |
| `runs_dir` | path | yes | `.local26/runs` | Run artifacts directory. |
| `logs_dir` | path | yes | `.local26/logs` | Log directory. |
| `lock_file` | path | yes | `.local26/local26.lock` | Global LOCAL-26 lock file. |
| `require_plan_for_deploy` | bool | yes | `true` | Enforces precomputed plans before deploy. |
| `fail_fast` | bool | yes | `true` | Stop on first error. |
| `max_parallel` | int | yes | `4` | Must be >= 1. |
| `shell` | path | yes | `/usr/bin/bash` | Execution shell. |

### `[tools]` (required)

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `ssh` | path | yes | `/usr/bin/ssh` | SSH executable path. |
| `rsync` | path | yes | `/usr/bin/rsync` | rsync executable path. |
| `find` | path | yes | `/usr/bin/find` | find executable path. |
| `jq` | path | no | none | Include only when available. |

### `[defaults]` (required)

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `rsync_opts` | string | yes | `-az` | Default rsync option string. |
| `backup` | bool | yes | `true` | Backup behavior default. |
| `backup_suffix` | string | yes | `.bkp` | Backup suffix default. |
| `remote_mkdir` | bool | yes | `true` | Ensure remote target directory exists. |
| `dry_run_default` | bool | yes | `false` | Dry run default behavior. |
| `log_hosts` | csv-string | yes | empty | Default host list for `local26 pull-logs`. |
| `log_dest_dir` | path | yes | `.local26/pulled-logs` | Local destination for pulled diagnostics. |
| `jboss_log_path` | path | yes | empty | Remote JBoss log path or glob for `pull-logs`. |
| `apache_log_path` | path | yes | empty | Remote Apache log path or glob for `pull-logs`. |
| `engin_log_path` | path | yes | empty | Remote Engin log path or glob for `pull-logs`. |
| `smartxfr_log_path` | path | yes | empty | Remote SmartXFR log path or glob for `pull-logs`. |

### `[routing]` (required)

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `env_from_filename_prefix` | map-string | yes | `s:sys,q:qa,p:production` | Comma-separated `prefix:env` map. |
| `env_from_server_name_char_at` | int | yes | `4` | 1-based character index. |
| `env_from_server_name_char_map` | map-string | yes | `s:sys,q:qa,p:production` | Comma-separated `char:env` map. |

### `[access]` (recommended)

Access policy is evaluated by `local26 deploy`, `local26 doctor`, and `local26 compliance report`.

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `allowed_users` | csv-string | no | empty | If set, only listed local usernames can deploy. |
| `allowed_groups` | csv-string | no | empty | If set, only members of at least one listed local group can deploy. |
| `denied_users` | csv-string | no | empty | Listed users are always denied. |
| `deny_root` | bool | no | `false` | When `true`, blocks deploy/compliance actor checks for UID 0. |
| `allow_remote_cmd` | bool | no | `true` | When `false`, deploy blocks selected plan steps with `type = remote_cmd`. |

Generated configs set `allow_remote_cmd = false` for least privilege. Runtime directories and generated run/state artifacts are always written owner-only by the runtime (`0700` directories and `0600` files). Existing configs without `[access]` continue to load, but `local26 doctor` and `local26 compliance report` warn that access policy is not configured.

### `[scope "NAME"]` (0..N)

Each scope section name is literal form `[scope "<scope-name>"]`.

Required keys:

| Key | Type | Required | Default | Notes |
|---|---|---:|---|---|
| `enabled` | bool | yes | `true` | Scope activation flag. |
| `source_dir` | path | yes | none | Source path to deploy from. |
| `target_dir` | path | yes | none | Destination path to deploy to. |
| `servers` | csv-string | yes | none | Comma-separated host list; no spaces around commas. |
| `discovery` | enum | yes | `mtime_since_last_success` | Allowed: `mtime_since_last_success` in v0.1. |

Optional keys:

| Key | Type | Required | Default |
|---|---|---:|---|
| `rsync_opts` | string | no | inherited from `[defaults].rsync_opts` |
| `backup` | bool | no | inherited from `[defaults].backup` |
| `backup_suffix` | string | no | inherited from `[defaults].backup_suffix` |

## Legacy import rules (`local26 init --import`)

Legacy `settings.cfg` import accepts:

- Section headers: `[NAME]`
- Assignments: `key=value` and `key = value`
- Leading/trailing whitespace around keys and values (trimmed)
- Blank lines and comment lines starting with `#` or `;` (ignored)

Legacy known keys:

- Required per section: `source_dir`, `target_dir`, `servers`
- Optional per section: `rsync_opts`, `backup`, `backup_suffix`
- Optional global keys (outside sections): `log_hosts`, `log_dest_dir`, `jboss_log_path`, `apache_log_path`, `engin_log_path`, `smartxfr_log_path`

Unknown legacy keys are ignored with a warning (one warning per unknown key name).

Import fails if any legacy section is missing required keys.
