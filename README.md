# Seraf

Seraf is a Python-based deployment and runbook control plane for file sync, plan generation, deploy execution, diagnostics, and operator workflows.

Feedback, issues, and borrowed workflow ideas are welcome — especially if they help make Seraf simpler, tougher, and easier for another operator to trust.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
seraf --help
```

## Common commands

```bash
seraf init --guided
seraf doctor
seraf plan --summary
seraf deploy --plan .seraf/plans/<plan>.plan.json --check --dry-run
seraf history --limit 5
seraf logs <run-id>
seraf pull --scope main --dry-run
seraf diag --hosts app01 --dry-run
seraf status
```

Guided setup writes both `.seraf/config.ini` for the current runtime and `.seraf/config.yaml` as a human-readable mirror.

## Repo layout

- `src/seraf`, Python implementation
- `bin/seraf`, shell compatibility wrapper
- `docs/`, operator docs
- `packaging/rpm/`, first RPM packaging scaffold

## Operator docs

Start here if another tech needs to pick it up quickly:

- `docs/quickstart.md`
- `docs/setup-guide.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/guided-setup.md`
- `docs/when-to-use-seraf.md`
- `examples/legacy-settings.cfg.example`
- `examples/profile-prod.yaml`
- `CONTRIBUTING.md`

## RPM packaging

A first RHEL-style packaging scaffold lives under `packaging/rpm/`.

See:

- `packaging/rpm/README.md`
- `packaging/rpm/seraf.spec`
- `packaging/rpm/build-rpm.sh`
