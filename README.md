# Local-26
![Local-26 IT operators union seal](docs/assets/local26-logo.png)

**Operators’ Local-26 — plan, deploy, audit, hold the line.**

Local-26 is a lean, operator-readable deployment and runbook control plane for file sync, plan generation, deploy execution, diagnostics, and security-conscious operator workflows.

Support the line: Local-26 tee and mug runs may be offered for the Union Locals morale and welfare fund.

Feedback, issues, and borrowed workflow ideas are welcome — especially if they help make Local-26 simpler, tougher, and easier for another operator to trust.

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
local26 --help
```

## Common commands

```bash
local26 init --guided
local26 doctor
local26 compliance report
local26 compliance inventory --scope all
local26 compliance harden-plan --scope linux --format markdown
local26 db doctor
local26 db inventory
local26 plan --summary
local26 deploy --plan .local26/plans/<plan>.plan.json --check --dry-run
local26 history --limit 5
local26 logs <run-id>
local26 pull --scope main --dry-run
local26 diag --hosts app01 --dry-run
local26 status
```

Guided setup writes both `.local26/config.ini` for the current runtime and `.local26/config.yaml` as a human-readable mirror.

## Database operations

Local-26 includes a database operations command group for configured Oracle 19c, PostgreSQL 17, and SQLite targets:

```bash
local26 db doctor
local26 db tools --engine postgres17
local26 db diag --target appdb
local26 db backup --target local-sqlite --backup-path .local26/db/app.db.bak --execute
local26 db audit --format json
```

Database targets are configured as `[database "NAME"]` sections in `.local26/config.ini` or under `databases:` in YAML. Oracle and PostgreSQL integrations are safe external-tool plans and discovery checks; SQLite diagnostics and backups use Python stdlib `sqlite3`. Mutating actions are dry-run/planned unless `--execute` is supplied, and secrets must be passed as environment variable names or external references.

## Compliance and hardening

Local-26 includes read-only operational checks mapped to selected NIST/CMS control themes for Local-26 access policy, Linux OS settings, web server configuration, Java/Tomcat, JavaScript, Node.js, and Angular projects:

```bash
local26 compliance report --scope all
local26 compliance inventory --path /srv/myapp --format json
local26 compliance harden-plan --scope web --path /srv/myapp --format markdown
```

The compliance scanners inspect local files and emit findings, inventory, and hardening recommendations. They do not certify compliance, run package installs, run online audits, call `sudo`, call `sysctl -w`, restart services, change permissions, or edit configs. `harden-plan` is advisory only; it writes suggested remediation steps but does not apply them.

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

- `src/local26`, Python implementation
- `bin/local26`, source-tree launcher
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
