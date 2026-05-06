# Seraf quickstart

Get a working Seraf project up in under 10 minutes.

## 1. Enter the project
```bash
cd /path/to/your/project
```

## 2. Run guided setup
```bash
seraf init --guided
```
Answer the prompts for:
- project name
- scope name
- source directory
- remote target directory
- servers
- safety defaults

Seraf writes `.seraf/config.ini`, mirrors it to `.seraf/config.yaml`, and creates the local state folders for you.

## 3. Check the environment
```bash
seraf doctor
```
If doctor reports warnings, read them before your first live deploy.

## 4. Build a plan
```bash
seraf plan --summary
```
This shows what Seraf found and how many deploy steps it intends to run.

## 5. Run a safe first deploy
For a bounded first pass, start with dry run mode:
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --dry-run --scope main
```
Then run the live deploy when the plan looks right:
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main --fail-fast
```

## 6. Check status
```bash
seraf status
```

## 7. Useful follow-up commands
Once the first plan/deploy path makes sense, these are the next commands worth learning:

```bash
seraf history --limit 5
seraf logs <run-id>
seraf pull --scope main --dry-run
seraf diag --hosts app01 --dry-run
```

## Good first habits
- keep `--fail-fast` on for early rollouts
- use `--dry-run` before touching production
- review plan summaries before deploy
- keep source and target paths explicit

## If you get stuck
Start with:
- `seraf doctor`
- `docs/troubleshooting.md`
