# When to use Seraf

Use Seraf when you want a lean, operator-readable deployment and runbook control plane for file sync, plan-first deploys, history, diagnostics, and repeatable shell-oriented workflows.

## Good fit
- small to medium deployment workflows
- rsync/ssh-based releases
- environments where operators want to inspect plans before running them
- teams that value explicit artifacts like plans, runs, and logs
- runbook-style deploys where readability matters as much as automation
- situations where you want a Python control plane with simple operational behavior

## Especially useful for
- internal apps
- multi-host file deployments
- repeatable config or content pushes
- guided setup for technicians who need a bounded first path
- pull-back workflows for logs or reverse sync
- remote diagnostics against known hosts

## Not the best fit
- giant platform orchestration with deep cloud-native control loops
- fully event-driven infra automation at massive scale
- teams that already need a heavyweight platform and all of its complexity
- browser/UI-first users who never want to touch a shell

## Decision test
Seraf is probably a good fit if you want:
- a plan before a deploy
- shell-friendly, auditable behavior
- simple artifacts on disk
- low ceremony
- the ability to debug what happened without guessing

## First commands to try
```bash
seraf init --guided
seraf doctor
seraf plan --summary
seraf deploy --plan .seraf/plans/<plan-id>.plan.json --dry-run --scope main
```

## Related docs
- `README.md`
- `docs/quickstart.md`
- `docs/setup-guide.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
