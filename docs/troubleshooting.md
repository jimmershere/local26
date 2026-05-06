# Troubleshooting

## `seraf doctor` reports missing binaries
Install or expose these on `PATH`:
- ssh
- rsync
- find
- sha256sum
- bash
- python3

Then rerun:
```bash
seraf doctor
```

## Guided setup stops before writing config
Usually one of these was missing:
- source directory
- target directory
- server list

Run `seraf init --guided` again and complete the missing answer.

## The source path does not exist yet
Seraf can keep a placeholder path in the config, but that is a warning sign. Confirm the real source path before a live deploy.

## `seraf plan --summary` shows zero files
Check:
- the source directory is correct
- files actually exist there
- scope filters are not excluding your target scope
- last-success state is not filtering out everything unexpectedly

## `seraf deploy` says it cannot find the plan file
Use the full path to the plan JSON, for example:
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main
```

## `seraf deploy` says no matching scopes were found
The `--scope` value must match a scope present in the plan. Recheck the scope name in `.seraf/config.ini` or `.seraf/config.yaml`, or regenerate the plan.

## A deploy step fails
Seraf writes the failing step into the latest run record. Inspect:
- terminal output
- `.seraf/runs/<run-id>/run.json`

Common causes:
- bad SSH access
- wrong target path
- missing remote directories
- rsync option mismatch

## Status is empty
If `seraf status` shows no completed runs yet, you have not run deploy successfully in this project. Start with:
```bash
seraf plan --summary
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --dry-run
```

## I want the safest first deploy possible
Use all of these together:
- backups enabled
- `max_parallel = 1`
- `seraf deploy --dry-run`
- `seraf deploy --fail-fast`

## `seraf pull` does not target the hosts I expected
Check:
- the scope name is correct
- the config or profile actually contains those hosts
- `--hosts` uses a comma-separated host list
- use `--dry-run` first before assuming Seraf will pull what you meant

## `seraf diag` feels too broad for a first try
Start smaller:
- pass one host with `--hosts`
- use `--dry-run`
- add `--pid` only when you know the target process
- keep duration short, for example `--duration 20s`

## Where to look when confused
In order:
1. `seraf doctor`
2. `seraf status`
3. latest plan JSON
4. latest run JSON
5. this troubleshooting guide
