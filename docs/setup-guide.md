# Local-26 setup guide

This guide walks a new operator from zero to a usable Phase 1 setup.

## What Local-26 needs
Local-26 is a textual deployment helper. For Phase 1, it helps you:
- create a project config
- inspect readiness
- generate a deploy plan
- run a bounded deploy
- review the latest result

## Before you start
Make sure these tools are available on the machine running Local-26:
- bash
- python3
- ssh
- rsync
- find
- sha256sum

## Project layout
Local-26 stores project-local files under `.local26/`:
- `config.ini` for the current runtime configuration
- `config.yaml` as a human-friendly mirror of the guided setup output
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
local26 init --guided
```
The guided flow is the easiest front door. It asks one decision at a time, covers hosts / rsync / backups, and shows a config preview before writing anything.

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
local26 doctor
```
Warnings are not always blockers, but failures usually are.

### Step 5: generate the first deploy plan
```bash
local26 plan --summary
```
This gives you a readable summary instead of a raw JSON dump.

### Step 6: do a dry run deploy
```bash
local26 deploy --plan .local26/plans/<plan-id>.plan.json --scope main --dry-run
```
Dry run mode is the safest way to verify the path before a live push.

### Step 7: run the live deploy
```bash
local26 deploy --plan .local26/plans/<plan-id>.plan.json --scope main --fail-fast
```

### Step 8: confirm the result
```bash
local26 status
```

## Legacy config import
If you already have an older settings file:
```bash
local26 init --import ./settings.cfg
```
Local-26 converts it into `.local26/config.ini` and creates the expected local directories. Guided setup also writes `.local26/config.yaml` for easier human review.

## Operator guidance
For early rollouts:
- prefer one scope first
- keep worker count low
- keep backups enabled
- use dry runs generously
- review the run record in `.local26/runs/`

## After the first deploy path works
The next operator commands to learn are:
- `local26 history --limit 5`
- `local26 logs <run-id>`
- `local26 pull --scope main --dry-run`
- `local26 diag --hosts app01 --dry-run`

## When something feels wrong
Do not guess. Use:
- `local26 doctor`
- `local26 status`
- the most recent `.local26/runs/*/run.json`
- `docs/troubleshooting.md`
