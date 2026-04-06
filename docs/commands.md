# SERAF Command Reference v0.1

## Overview

```
seraf init [--import PATH] [--force] [--project NAME]
seraf plan [--scope NAME] [--format json] [--stdout] [--ci] [--summary]
seraf deploy --plan PATH [options]
seraf deploy --latest [options]
seraf status
seraf doctor [--plan PATH]
seraf help
```

---

## `seraf init`

Initializes the `.seraf/` workspace directory structure and generates `config.ini` by importing a legacy `settings.cfg` or a modern config.

| Flag | Description |
|---|---|
| `--import PATH` | Path to legacy or modern config to import |
| `--force` | Overwrite existing `.seraf/config.ini` |
| `--project NAME` | Override project name in generated config |

---

## `seraf plan`

Generates a deployment plan from `.seraf/config.ini` and writes it to `.seraf/plans/`.

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

The plan file is still written to `.seraf/plans/` unless `--ci` is also set.

Example output:
```
scope:web:0001 | mkdir | - | pending
scope:web:0002 | rsync | - | pending
scope:web:0003 | rsync | 30 | pending
```

---

## `seraf deploy`

Executes a deployment plan.

| Flag | Description |
|---|---|
| `--plan PATH` | Path to a specific `.plan.json` file |
| `--latest` | Use the most recently generated plan file |
| `--dry-run` | Print steps without executing |
| `--scope NAME` | Execute only steps for the named scope |
| `--max-parallel N` | Max concurrent background workers (default: 4) |
| `--step-timeout SECS` | Default timeout per step in seconds (0 = none) |
| `--rollback-on-failure` | On failure, execute rollback cmds for successful prior steps |
| `--fail-fast` / `--no-fail-fast` | Override `fail_fast` from config |

---

## `seraf status`

Shows the current deployment run state:

- Any active runs (in-progress, based on presence of run.json in run dirs)
- Last run result (pass/fail)
- Last run timestamp
- Last run ID

**State sources (in order of priority):**

1. `~/.seraf/state.json` — global state file (written by external integrations)
2. `/tmp/seraf-state.json` — fallback temp state file
3. `.seraf/runs/` — scans the latest `run.json` in the local project

**State file format** (`~/.seraf/state.json`):
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
=== seraf status ===

Active runs:
  (none)

Last run:
  run_id    : 20260101T000000Z-12345
  result    : pass
  exit_code : 0
  timestamp : 2026-01-01T00:01:00Z
```

---

## `seraf doctor`

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
| `dir:~/.seraf` | PASS/WARN | global state dir readable+writable |
| `dir:.seraf` | PASS/WARN | project workspace dir |
| `dir:.seraf/plans` | PASS/WARN | plans dir |
| `dir:.seraf/runs` | PASS/WARN | runs dir |
| `dir:.seraf/state` | PASS/WARN | state dir |
| `plan:json` | PASS/FAIL | plan file parses as valid JSON |
| `plan:schema` | PASS/FAIL | required top-level keys present |
| `plan:kind` | PASS/FAIL | `kind == "plan"` |
| `plan:mode` | PASS/FAIL | `mode == "deploy"` |
| `plan:schema_ver` | PASS/FAIL | `schema == "seraf.plan.v0.1"` |
| `plan:scopes` | PASS/WARN | scopes list present and non-empty |
| `plan:steps` | PASS/WARN | total step count across all scopes |

**Output format:**
```
[PASS] binary:bash: /bin/bash
[PASS] binary:python3: /usr/bin/python3
[WARN] dir:.seraf: does not exist
[FAIL] plan:kind: expected 'plan', got 'notaplan'
```

Exit code: `0` if all checks pass, `1` if any check is FAIL.
