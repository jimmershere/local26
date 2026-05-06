# Guided setup

`seraf init --guided` is the cleanest way to start a new project.

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

At the end, Seraf writes:
- `.seraf/config.ini` — current runtime config used by the Phase 1 commands
- `.seraf/config.yaml` — human-friendly mirror of the same setup
- `.seraf/state/<scope>.json`
- `.seraf/plans/`, `.seraf/runs/`, and `.seraf/logs/`

## Typical flow

```bash
cd /path/to/project
seraf init --guided
seraf doctor
seraf plan --summary
```

## Notes

- If the source path does not exist yet, Seraf can keep it as a placeholder.
- If the preview looks wrong, choose `edit` and run through the interview again.
- For a first live deploy, keep backups on and worker count low.
