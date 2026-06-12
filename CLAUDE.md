# CLAUDE.md

Guidance for AI agents and contributors working in this repository.

## What Local-81 is

Local-81 is a lean, **operator-readable deploy and runbook control plane**, written
as a Python 3.12+ CLI. It is **push-based over SSH + rsync** — not an agent daemon.
A control node runs `local81`; target hosts only need `sshd`, `python3`, `rsync`,
`find`, and `sha256sum`.

## Architecture map

- `src/local81/cli.py` — argparse entrypoint (`local81 = local81.cli:main`).
- `src/local81/commands/` — one module per command group: `init`, `doctor`,
  `plan`, `deploy`, `pull`, `pull_logs`, `diag`, `db`, `compliance`, `history`,
  `logs`, `status`, `profiles`, `hooks`, `diff`, `guided`.
- `src/local81/db/` — DB readiness/diag/backup for Oracle 19c, Postgres 17, SQLite.
- `src/local81/compliance/` — read-only NIST/CMS-themed hardening scanners.
- `src/local81/{config,state,models,runner,paths,policy,plan_integrity,...}.py` —
  core: config parsing/validation, run state, plan/exec runner, access policy.
- `bin/local81` — source-tree launcher dispatching into the Python CLI.
- `.local81/` (runtime) — `config.ini` + `config.yaml`, `plans/`, `runs/`, `state/`,
  `logs/`. Artifacts are owner-only (`0700` dirs, `0600` files).
- `docs/` — operator docs + `config-schema.md`, `plan-schema.md`, `commands.md`.
- `packaging/` — Debian + RPM scaffolds.

## How to verify changes

```bash
make test          # compile + baseline shell regression suite
make python-test   # pytest suite (needs .[dev])
make quality       # compile + security-check + lint + format-check + pytest
make full-shell-test  # every shell test (includes advanced/in-progress)
```

CI (`.github/workflows/ci.yml`) runs `make test`, `make python-test`, and
`make quality` on Python 3.12 and 3.13.

## Project conventions

- Mutating actions (deploy, `db backup`, etc.) are **dry-run / planned unless
  `--execute`** is supplied.
- **Secrets are never literals**: pass environment-variable names or external
  references, never raw passwords/tokens in config or plans.
- Config is strictly schema-validated by `doctor` and `deploy --check`; unknown
  sections/keys are errors.

## Cross-phase guardrails (from the improvement plan)

- **Stdlib-first.** Every new runtime dependency needs a one-line justification
  in the PR.
- **No phase may break** the shell regression suite or v1 plan compatibility.
- **Operator-readability is a feature.** On-disk artifacts stay human-greppable;
  any index/DB indexes files, it never replaces them.
- **Honesty over magic.** Non-idempotent, non-rollbackable, and always-run steps
  are labeled, never hidden.
- **Secrets never at rest** in anything Local-81 writes (plans, manifests, logs).
