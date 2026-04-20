# Seraf setup guide

This guide walks a new operator from zero to a usable Phase 1 setup.

## What Seraf needs
Seraf is a textual deployment helper. For Phase 1, it helps you:
- create a project config
- inspect readiness
- generate a deploy plan
- run a bounded deploy
- review the latest result

## Before you start
Make sure these tools are available on the machine running Seraf:
- bash
- python3
- ssh
- rsync
- find
- sha256sum

## Project layout
Seraf stores project-local files under `.seraf/`:
- `config.ini` for configuration
- `state/` for per-scope state
- `plans/` for generated plans
- `runs/` for deploy records
- `logs/` for future diagnostics

## Recommended first-time setup
### Step 1: move into the source project
```bash
cd /path/to/project
```

### Step 2: create the config with guided setup
```bash
seraf init --guided
```
The guided flow is the easiest front door. It asks one decision at a time and shows a config preview before writing anything.

### Step 3: read the preview carefully
Double-check:
- source directory
- target directory
- server list
- backup settings
- parallelism

If anything looks off, choose `edit` and run through the interview again.

### Step 4: run environment checks
```bash
seraf doctor
```
Warnings are not always blockers, but failures usually are.

### Step 5: generate the first deploy plan
```bash
seraf plan --summary
```
This gives you a readable summary instead of a raw JSON dump.

### Step 6: do a dry run deploy
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main --dry-run
```
Dry run mode is the safest way to verify the path before a live push.

### Step 7: run the live deploy
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main --fail-fast
```

### Step 8: confirm the result
```bash
seraf status
```

## Legacy config import
If you already have an older settings file:
```bash
seraf init --import ./settings.cfg
```
Seraf converts it into `.seraf/config.ini` and creates the expected local directories.

## Operator guidance
For early rollouts:
- prefer one scope first
- keep worker count low
- keep backups enabled
- use dry runs generously
- review the run record in `.seraf/runs/`

## When something feels wrong
Do not guess. Use:
- `seraf doctor`
- `seraf status`
- the most recent `.seraf/runs/*/run.json`
- `docs/troubleshooting.md`
