# LOCAL-81 Command Reference v0.1

## Overview

```
local81 init [--import PATH] [--force] [--project NAME] [--guided]
local81 doctor [--plan PATH]
local81 compliance report
local81 status
local81 hooks
local81 profiles
local81 profile create NAME
local81 plan [--scope NAME] [--format json] [--stdout] [--ci] [--summary]
local81 deploy (--plan PATH | --latest) [options]
local81 pull [--scope NAME] [--hosts host1,host2] [--rsync-opts OPTS] [--dry-run]
local81 history [--limit N]
local81 pull-logs [options]
local81 diag [options]
local81 logs RUN_ID
local81 diff PLAN_A PLAN_B
```

Global option:

```
local81 --profile PROFILE <command>
```
Use `--profile` to apply a profile overlay from `.local81/profiles/` when the command supports it.

---

## `local81 init`

Initializes the `.local81/` workspace directory structure and generates `config.ini` by importing a legacy `settings.cfg` or a modern config. Guided mode also writes a matching `config.yaml` mirror.

| Flag | Description |
|---|---|
| `--import PATH` | Path to legacy or modern config to import |
| `--force` | Overwrite existing `.local81/config.ini` |
| `--project NAME` | Override project name in generated config |
| `--guided` | Launch the interactive guided setup flow instead of importing config |

---

## `local81 plan`

Generates a deployment plan from `.local81/config.ini` and writes it to `.local81/plans/`.

| Flag | Description |
|---|---|
| `--scope NAME` | Restrict plan to a single scope |
| `--format json` | Output format (only `json` supported) |
| `--stdout` | Print plan JSON to stdout in addition to writing file |
| `--ci` | Print plan JSON to stdout only, skip writing file |
| `--summary` | Print a compact one-liner per step instead of full JSON |

### `--summary` output format

When `--summary` is specified, one line per step is printed to stdout:

```
step_id | type | timeout | status
```

- `step_id` — stable step identifier (e.g. `scope:myapp:0001`)
- `type` — step type: `mkdir`, `rsync`, or `remote_cmd`
- `timeout` — per-step timeout in seconds, or `-` if not set
- `status` — always `pending` for a newly generated plan

The plan file is still written to `.local81/plans/` unless `--ci` is also set.

Example output:
```
scope:web:0001 | mkdir | - | pending
scope:web:0002 | rsync | - | pending
scope:web:0003 | rsync | 30 | pending
```

---

## `local81 deploy`

Executes a deployment plan.

Before any steps run, deploy enforces the configured `[access]` policy from `.local81/config.ini`. A deploy is blocked when the current operator is denied by user/group policy or when selected plan steps include `remote_cmd` while `access.allow_remote_cmd = false`.

| Flag | Description |
|---|---|
| `--plan PATH` | Path to a specific `.plan.json` file |
| `--latest` | Use the most recently generated plan file |
| `--dry-run` | Print steps without executing |
| `--scope NAME` | Execute only steps for the named scope |
| `--max-parallel N` | Max concurrent workers (CLI default: 1) |
| `--step-timeout SECS` | Default timeout per step in seconds |
| `--rollback-on-failure` | On failure, execute rollback cmds for successful prior steps |
| `--fail-fast` / `--no-fail-fast` | Override `fail_fast` behavior |
| `--check` | Validate the plan and execution inputs before running steps |
| `--hosts-file PATH` | Restrict execution to hosts listed in a file |
| `--parallel` | Enable parallel host execution where supported |
| `--notify` | Emit notification output for wrapped/operator workflows |
| `--quiet` | Reduce normal progress chatter |

### Recommended first live deploy

```bash
local81 deploy --plan .local81/plans/<plan-id>.plan.json --scope main --dry-run --fail-fast
local81 deploy --plan .local81/plans/<plan-id>.plan.json --scope main --fail-fast
```

---

## `local81 status`

Shows the current deployment run state:

- Any active runs (in-progress, based on presence of run.json in run dirs)
- Last run result (pass/fail)
- Last run timestamp
- Last run ID

**State sources (in order of priority):**

1. `~/.local81/state.json` — global state file (written by external integrations)
2. `/tmp/local81-state.json` — fallback temp state file
3. `.local81/runs/` — scans the latest `run.json` in the local project

**State file format** (`~/.local81/state.json`):
```json
{
  "last_run_id": "20260101T000000Z-12345",
  "last_result": "pass",
  "last_run_at": "2026-01-01T00:01:00Z",
  "last_rc": 0
}
```

Example output:
```
Local-81 status
============

Active runs:
  None right now.

Latest run:
  Run ID: 20260101T000000Z-12345
  Result: pass
  Exit code: 0
  Finished: 2026-01-01T00:01:00Z
```

---

## `local81 pull`

Pulls files back from remote hosts using the current project config.

| Flag | Description |
|---|---|
| `--scope NAME` | Restrict pull to a named scope |
| `--hosts host1,host2` | Restrict to specific hosts |
| `--rsync-opts OPTS` | Extra rsync options to append |
| `--dry-run` | Print the pull actions without executing |

Use this when you need reverse sync from a remote system back into the local workspace.

---

## `local81 history`

Shows recent deployment runs, newest first.

| Flag | Description |
|---|---|
| `--limit N` | Maximum number of runs to show (default: 20) |

---

## `local81 pull-logs`

Collects remote application logs into a local destination folder.

| Flag | Description |
|---|---|
| `--settings PATH` | Legacy settings file to read (default: `./settings.cfg`) |
| `--hosts host1,host2` | Restrict to specific hosts |
| `--dest PATH` | Local destination directory |
| `--jboss-path PATH` | Override JBoss log path |
| `--apache-path PATH` | Override Apache log path |
| `--engin-path PATH` | Override Engin log path |
| `--smartxfr-path PATH` | Override SmartXfr log path |

---

## `local81 diag`

Runs remote diagnostics against one or more hosts.

| Flag | Description |
|---|---|
| `--project NAME` | Project label for the diagnostic bundle |
| `--hosts host1,host2` | Restrict to specific hosts |
| `--diag-type TYPE` | Diagnostic type, for example `strace` |
| `--pid PID` | Process ID for targeted diagnostics |
| `--duration VALUE` | Capture duration, for example `20s` |
| `--remote-cmd CMD` | Custom remote command override |
| `--out-dir PATH` | Local output directory |
| `--ssh-user USER` | Override SSH user |
| `--include-disabled` | Include hosts marked disabled in config |
| `--dry-run` | Print the diagnostic actions without executing |

---

## `local81 logs`

Shows detailed step-by-step output for a single run. `RUN_ID` may be a full run ID or an unambiguous prefix.

---

## `local81 diff`

Compares two generated plan files.

Usage:

```bash
local81 diff .local81/plans/old.plan.json .local81/plans/new.plan.json
```

Use this when you want a quick before/after check on plan generation changes.

---

## `local81 hooks`

Lists supported hook paths and whether each hook is installed and executable.

---

## `local81 profiles`

Lists available profile overlays from `.local81/profiles/`.

---

## `local81 profile create`

Creates a scaffold profile file at `.local81/profiles/<name>.yaml`.

---

## `local81 doctor`

Checks environment health and optionally validates a plan file schema.

| Flag | Description |
|---|---|
| `--plan PATH` | Path to a `.plan.json` file to validate |

**Checks performed:**

| Check | Level | Description |
|---|---|---|
| `binary:bash` | PASS/FAIL | bash in PATH |
| `binary:python3` | PASS/FAIL | python3 in PATH |
| `binary:ssh` | PASS/FAIL | ssh in PATH |
| `binary:rsync` | PASS/FAIL | rsync in PATH |
| `binary:find` | PASS/FAIL | find in PATH |
| `binary:sha256sum` | PASS/FAIL | sha256sum in PATH |
| `binary:git` | PASS/WARN | git in PATH (warn if missing; only required for `workspace=git`) |
| `dir:~/.local81` | PASS/WARN | global state dir readable+writable |
| `dir:.local81` | PASS/WARN | project workspace dir |
| `dir:.local81/plans` | PASS/WARN | plans dir |
| `dir:.local81/runs` | PASS/WARN | runs dir |
| `dir:.local81/state` | PASS/WARN | state dir |
| `plan:json` | PASS/FAIL | plan file parses as valid JSON |
| `plan:schema` | PASS/FAIL | required top-level keys present |
| `plan:kind` | PASS/FAIL | `kind == "plan"` |
| `plan:mode` | PASS/FAIL | `mode == "deploy"` |
| `plan:schema_ver` | PASS/FAIL | `schema == "local81.plan.v0.1"` |
| `plan:scopes` | PASS/WARN | scopes list present and non-empty |
| `plan:steps` | PASS/WARN | total step count across all scopes |

**Output format:**
```
[PASS] binary:bash: /bin/bash
[PASS] binary:python3: /usr/bin/python3
[WARN] dir:.local81: does not exist
[FAIL] plan:kind: expected 'plan', got 'notaplan'
```

Exit code: `0` if all checks pass, `1` if any check is FAIL.

---

## `local81 compliance report`

Prints a NIST/CMS-style operational hardening report focused on access control and least privilege.

The report includes:

| Finding | Control theme | Description |
|---|---|---|
| `[access]` loaded | AC-3 | Confirms whether an access policy is configured |
| Allowed users/groups | AC-2 | Warns when deploy access is unrestricted |
| Root execution policy | AC-6 | Warns unless `deny_root = true` |
| Remote command policy | CM-5 | Passes when `allow_remote_cmd = false` |
| Runtime/artifact permissions | AC-6 | Confirms directories/files are owner-only by design |

Exit code: `0` unless any finding is FAIL. A FAIL usually means the current actor is denied by policy.
