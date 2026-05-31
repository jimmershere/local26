# Troubleshooting

## `local26 doctor` reports missing binaries
Install or expose these on `PATH`:
- ssh
- rsync
- find
- sha256sum
- bash
- python3

Then rerun:
```bash
local26 doctor
```

## Guided setup stops before writing config
Usually one of these was missing:
- source directory
- target directory
- server list

Run `local26 init --guided` again and complete the missing answer.

## The source path does not exist yet
Local-26 can keep a placeholder path in the config, but that is a warning sign. Confirm the real source path before a live deploy.

## `local26 plan --summary` shows zero files
Check:
- the source directory is correct
- files actually exist there
- scope filters are not excluding your target scope
- last-success state is not filtering out everything unexpectedly

## `local26 deploy` says it cannot find the plan file
Use the full path to the plan JSON, for example:
```bash
local26 deploy --plan .local26/plans/<plan-id>.plan.json --scope main
```

## `local26 deploy` says no matching scopes were found
The `--scope` value must match a scope present in the plan. Recheck the scope name in `.local26/config.ini` or `.local26/config.yaml`, or regenerate the plan.

## A deploy step fails
Local-26 writes the failing step into the latest run record. Inspect:
- terminal output
- `.local26/runs/<run-id>/run.json`

Common causes:
- bad SSH access
- wrong target path
- missing remote directories
- rsync option mismatch

## Status is empty
If `local26 status` shows no completed runs yet, you have not run deploy successfully in this project. Start with:
```bash
local26 plan --summary
local26 deploy --plan .local26/plans/<plan-id>.plan.json --dry-run
```

## I want the safest first deploy possible
Use all of these together:
- backups enabled
- `max_parallel = 1`
- `local26 deploy --dry-run`
- `local26 deploy --fail-fast`

## `local26 pull` does not target the hosts I expected
Check:
- the scope name is correct
- the config or profile actually contains those hosts
- `--hosts` uses a comma-separated host list
- use `--dry-run` first before assuming Local-26 will pull what you meant

## `local26 diag` feels too broad for a first try
Start smaller:
- pass one host with `--hosts`
- use `--dry-run`
- add `--pid` only when you know the target process
- keep duration short, for example `--duration 20s`

## Where to look when confused
In order:
1. `local26 doctor`
2. `local26 status`
3. latest plan JSON
4. latest run JSON
5. this troubleshooting guide
