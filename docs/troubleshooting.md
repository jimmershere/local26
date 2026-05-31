# Troubleshooting

## `local81 doctor` reports missing binaries
Install or expose these on `PATH`:
- ssh
- rsync
- find
- sha256sum
- bash
- python3

Then rerun:
```bash
local81 doctor
```

## Guided setup stops before writing config
Usually one of these was missing:
- source directory
- target directory
- server list

Run `local81 init --guided` again and complete the missing answer.

## The source path does not exist yet
Local-81 can keep a placeholder path in the config, but that is a warning sign. Confirm the real source path before a live deploy.

## `local81 plan --summary` shows zero files
Check:
- the source directory is correct
- files actually exist there
- scope filters are not excluding your target scope
- last-success state is not filtering out everything unexpectedly

## `local81 deploy` says it cannot find the plan file
Use the full path to the plan JSON, for example:
```bash
local81 deploy --plan .local81/plans/<plan-id>.plan.json --scope main
```

## `local81 deploy` says no matching scopes were found
The `--scope` value must match a scope present in the plan. Recheck the scope name in `.local81/config.ini` or `.local81/config.yaml`, or regenerate the plan.

## A deploy step fails
Local-81 writes the failing step into the latest run record. Inspect:
- terminal output
- `.local81/runs/<run-id>/run.json`

Common causes:
- bad SSH access
- wrong target path
- missing remote directories
- rsync option mismatch

## Status is empty
If `local81 status` shows no completed runs yet, you have not run deploy successfully in this project. Start with:
```bash
local81 plan --summary
local81 deploy --plan .local81/plans/<plan-id>.plan.json --dry-run
```

## I want the safest first deploy possible
Use all of these together:
- backups enabled
- `max_parallel = 1`
- `local81 deploy --dry-run`
- `local81 deploy --fail-fast`

## `local81 pull` does not target the hosts I expected
Check:
- the scope name is correct
- the config or profile actually contains those hosts
- `--hosts` uses a comma-separated host list
- use `--dry-run` first before assuming Local-81 will pull what you meant

## `local81 diag` feels too broad for a first try
Start smaller:
- pass one host with `--hosts`
- use `--dry-run`
- add `--pid` only when you know the target process
- keep duration short, for example `--duration 20s`


## `local81 db doctor` says no targets matched
Add `[database "NAME"]` sections to `.local81/config.ini` or a `databases:` mapping in `.local81/config.yaml`. Make sure each target has `engine = oracle19c`, `engine = postgres17`, or `engine = sqlite`, and that `enabled` is not set to `false`.

## `local81 db` reports missing Oracle or PostgreSQL tools
Oracle and PostgreSQL support wraps installed CLIs. Install the relevant client tools on the operator or managed host:
- Oracle: SQL*Plus or SQLcl, RMAN, Data Pump, ADRCI, listener tools, AHF/ORAchk where supportable
- PostgreSQL: `psql`, `pg_dump`, `pg_basebackup`, Barman or pgBackRest, exporters, pgBadger

Missing tools are warnings unless a live operational workflow depends on them.

## `local81 db backup` did not create a SQLite backup
SQLite backups require both an explicit destination and execution approval:

```bash
local81 db backup --target local-cache --backup-path .local81/db/local-cache.bak --execute
```

Without `--execute`, Local-81 only writes a backup plan.

## `local81 compliance report` exits nonzero
By default, `report` exits nonzero when a failed finding is `high` or `critical`. To review findings without failing the command, run:

```bash
local81 compliance report --fail-on never
```

To reduce noise while reviewing gaps, add `--no-include-passed`.

## Where to look when confused
In order:
1. `local81 doctor`
2. `local81 status`
3. latest plan JSON
4. latest run JSON
5. this troubleshooting guide
