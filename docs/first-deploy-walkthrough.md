# First deploy walkthrough

This walkthrough assumes a simple Phase 1 setup with one scope named `main`.

## 1. Initialize the project
```bash
seraf init --guided
```
Suggested first answers:
- scope: `main`
- backups: `yes`
- fail fast: `yes`
- max parallel: `1`

That gives you a cautious first rollout.

## 2. Run doctor
```bash
seraf doctor
```
You want a clean result or only minor warnings before the first live deploy.

## 3. Generate the plan summary
```bash
seraf plan --summary
```
Look for:
- the correct scope name
- the right servers
- the expected file count
- a believable step count

## 4. Find the plan file
If you need the full plan path:
```bash
ls -1 .seraf/plans/*.plan.json | tail -n1
```

## 5. Run a dry run first
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main --dry-run
```
This records a run without executing remote commands.

## 6. Run the live deploy
```bash
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --scope main --fail-fast
```
What to expect:
- Seraf shows the selected plan and scope
- each step is announced as it runs
- failures are called out clearly
- a run record is written under `.seraf/runs/<run-id>/run.json`

## 7. Confirm the outcome
```bash
seraf status
```
If the deploy succeeded, you should see the latest run ID and result.

## 8. If deploy fails
1. read the failing step in terminal output
2. open the latest run record
3. fix the underlying issue
4. generate a fresh plan if the source changed
5. rerun deploy

## Useful files after the first deploy
- `.seraf/config.ini`
- `.seraf/plans/*.plan.json`
- `.seraf/runs/*/run.json`
- `.seraf/state/*.json`
