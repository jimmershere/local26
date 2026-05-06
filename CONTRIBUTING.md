# Contributing to Seraf

Thanks for taking a look at Seraf.

Seraf is meant to be practical, operator-friendly, and easy to reason about under pressure. Contributions are welcome when they make the tool simpler, tougher, clearer, or more useful for real deployment work.

## Good contribution types
- bug fixes
- doc corrections
- operator workflow improvements
- safer defaults
- better diagnostics
- sharper tests
- examples that help another tech get moving quickly

## Ground rules
- keep changes focused
- prefer simple behavior over cleverness
- update docs when CLI behavior changes
- add or adjust tests for non-trivial changes
- keep operator output readable
- be polite and concrete in issues, PRs, and suggestions

## Local setup
```bash
cd /path/to/seraf
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
```

## Verify before proposing changes
```bash
pytest -q
python -m seraf.cli --help
python -m seraf.cli doctor --help
python -m seraf.cli deploy --help
```

For workflow additions, also verify the affected command help directly, for example:
```bash
python -m seraf.cli pull --help
python -m seraf.cli diag --help
python -m seraf.cli pull-logs --help
python -m seraf.cli diff --help
```

## Docs to keep in sync
When command behavior changes, review these files together:
- `README.md`
- `docs/commands.md`
- `docs/quickstart.md`
- `docs/setup-guide.md`
- `docs/troubleshooting.md`
- `docs/guided-setup.md` when guided flow changes

## Examples and fit
Before adding a feature, read:
- `docs/when-to-use-seraf.md`
- `examples/legacy-settings.cfg.example`
- `examples/profile-prod.yaml`

## Suggested contribution flow
1. open an issue or note the problem clearly
2. make a focused branch or local change set
3. update tests and docs together
4. run verification commands
5. submit a PR or clean patch with rationale

## What helps maintainers most
- exact command used
- expected behavior
- actual behavior
- relevant config snippet
- relevant run/log artifact
- smallest reproducible example
