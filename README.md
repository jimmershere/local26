# Local-26
![Local-26 faux union seal](docs/assets/local26-logo.svg)

**Operators’ Local-26 — plan, deploy, audit, hold the line.**

Local-26 is a lean, operator-readable deployment and runbook control plane for file sync, plan generation, deploy execution, diagnostics, and security-conscious operator workflows.

Feedback, issues, and borrowed workflow ideas are welcome — especially if they help make Local-26 simpler, tougher, and easier for another operator to trust.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
local26 --help
```

## Common commands

```bash
local26 init --guided
local26 doctor
local26 compliance report
local26 plan --summary
local26 deploy --plan .local26/plans/<plan>.plan.json --check --dry-run
local26 history --limit 5
local26 logs <run-id>
local26 pull --scope main --dry-run
local26 diag --hosts app01 --dry-run
local26 status
```

Guided setup writes both `.local26/config.ini` for the current runtime and `.local26/config.yaml` as a human-readable mirror.

## Repo layout

- `src/local26`, Python implementation
- `bin/local26`, source-tree launcher
- `bin/seraf`, deprecated compatibility wrapper for the old command name
- `docs/`, operator docs
- `packaging/rpm/`, first RPM packaging scaffold

## Operator docs

Start here if another tech needs to pick it up quickly:

- `docs/quickstart.md`
- `docs/setup-guide.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/guided-setup.md`
- `docs/when-to-use-local26.md`
- `examples/legacy-settings.cfg.example`
- `examples/profile-prod.yaml`
- `CONTRIBUTING.md`

## RPM packaging

A first RHEL-style packaging scaffold lives under `packaging/rpm/`.

See:

- `packaging/rpm/README.md`
- `packaging/rpm/local26.spec`
- `packaging/rpm/build-rpm.sh`
