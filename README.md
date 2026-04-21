# Seraf

Seraf is a Python-based deployment and runbook control plane for file sync, plan generation, deploy execution, diagnostics, and operator workflows.

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
seraf plan --stdout
seraf deploy --plan .seraf/plans/<plan>.plan.json --check
seraf status
```

## Repo layout

- `src/seraf`, Python implementation
- `bin/seraf`, shell compatibility wrapper
- `docs/`, operator docs
- `packaging/rpm/`, first RPM packaging scaffold

## RPM packaging

A first RHEL-style packaging scaffold lives under `packaging/rpm/`.

See:

- `packaging/rpm/README.md`
- `packaging/rpm/seraf.spec`
- `packaging/rpm/build-rpm.sh`
