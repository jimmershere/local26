# Guided setup

`local26 init --guided` is the cleanest way to start a new project.

## What it asks

The interview walks through one bounded first-deploy path:
- project name
- default scope name
- local source directory
- remote target directory
- target host list
- rsync options
- backup behavior
- max parallel workers
- optional log hosts and log paths

## What it writes

At the end, Local-26 writes:
- `.local26/config.ini` — current runtime config used by the Phase 1 commands
- `.local26/config.yaml` — human-friendly mirror of the same setup
- `.local26/state/<scope>.json`
- `.local26/plans/`, `.local26/runs/`, and `.local26/logs/`

## Typical flow

```bash
cd /path/to/project
local26 init --guided
local26 doctor
local26 plan --summary
```

## Notes

- If the source path does not exist yet, Local-26 can keep it as a placeholder.
- If the preview looks wrong, choose `edit` and run through the interview again.
- For a first live deploy, keep backups on and worker count low.
