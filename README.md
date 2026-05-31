# Local-81
![Local-81 faux union seal](docs/assets/local81-logo.svg)

**Operators’ Local-81 — plan, deploy, audit, hold the line.**

Local-81 is a lean, operator-readable deployment and runbook control plane for file sync, plan generation, deploy execution, diagnostics, and security-conscious operator workflows.

Feedback, issues, and borrowed workflow ideas are welcome — especially if they help make Local-81 simpler, tougher, and easier for another operator to trust.

## Requirements

- Python 3.12 or newer
- bash
- ssh
- rsync
- find
- sha256sum

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
local81 --help
```

## Common commands

```bash
local81 init --guided
local81 doctor
local81 compliance report
local81 plan --summary
local81 deploy --plan .local81/plans/<plan>.plan.json --check --dry-run
local81 history --limit 5
local81 logs <run-id>
local81 pull --scope main --dry-run
local81 diag --hosts app01 --dry-run
local81 status
```

Guided setup writes both `.local81/config.ini` for the current runtime and `.local81/config.yaml` as a human-readable mirror.

## Verify a fresh clone

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
make test
make python-test
make quality
```

`make test` runs Python compile checks and the deterministic baseline shell regression suite. `make python-test` runs the Python pytest suite when development dependencies are installed. `make quality` runs compile, lint, format, pytest, and repository security gates. `make full-shell-test` runs every shell test, including advanced behavior tests that may be refined in later hardening phases.

## Repo layout

- `src/local81`, Python implementation
- `bin/local81`, source-tree launcher
- `docs/`, operator docs
- `packaging/rpm/`, first RPM packaging scaffold

## Operator docs

Start here if another tech needs to pick it up quickly:

- `docs/quickstart.md`
- `docs/setup-guide.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/guided-setup.md`
- `docs/when-to-use-local81.md`
- `examples/legacy-settings.cfg.example`
- `examples/profile-prod.yaml`
- `CONTRIBUTING.md`

## RPM packaging

A first RHEL-style packaging scaffold lives under `packaging/rpm/`.

See:

- `packaging/rpm/README.md`
- `packaging/rpm/local81.spec`
- `packaging/rpm/build-rpm.sh`
