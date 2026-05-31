# Local-81 quickstart

Get a working Local-81 project up in under 10 minutes.

## 1. Enter the project
```bash
cd /path/to/your/project
```

## 2. Run guided setup
```bash
local81 init --guided
```
Answer the prompts for:
- project name
- scope name
- source directory
- remote target directory
- servers
- safety defaults

Local-81 writes `.local81/config.ini`, mirrors it to `.local81/config.yaml`, and creates the local state folders for you.

## 3. Check the environment
```bash
local81 doctor
```
If doctor reports warnings, read them before your first live deploy.

## 4. Build a plan
```bash
local81 plan --summary
```
This shows what Local-81 found and how many deploy steps it intends to run.

## 5. Run a safe first deploy
For a bounded first pass, start with dry run mode:
```bash
local81 deploy --plan .local81/plans/<plan-id>.plan.json --dry-run --scope main
```
Then run the live deploy when the plan looks right:
```bash
local81 deploy --plan .local81/plans/<plan-id>.plan.json --scope main --fail-fast
```

## 6. Check status
```bash
local81 status
```

## 7. Useful follow-up commands
Once the first plan/deploy path makes sense, these are the next commands worth learning:

```bash
local81 history --limit 5
local81 logs <run-id>
local81 pull --scope main --dry-run
local81 diag --hosts app01 --dry-run
```

## Good first habits
- keep `--fail-fast` on for early rollouts
- use `--dry-run` before touching production
- review plan summaries before deploy
- keep source and target paths explicit

## If you get stuck
Start with:
- `local81 doctor`
- `docs/troubleshooting.md`
