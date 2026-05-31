# SF integration notes

- 2026-04-21: Migrated the next missing Python CLI handler, `pull`, from the shell wrapper into `src/local26/commands/pull.py`.
- Added CLI wiring for `local26 pull --scope/--hosts/--rsync-opts/--dry-run` in `src/local26/cli.py`.
- Added unit coverage in `tests/test_python_pull.py` for command formatting, dry-run host overrides, real-run subprocess invocation, disabled-scope behavior, missing-scope failure, and parser flags.
- Verified existing shell parity test still passes: `bash tests/test_pull.sh`.
- Note: I attempted to reach the requested Ollama endpoint at `http://192.168.1.206:11434`, but it did not respond within the local command timeout, so the implementation proceeded via direct repo inspection and parity testing.

- 2026-04-22: Migrated the next missing Python CLI handler, `diag`, from the shell wrapper into `src/local26/commands/diag.py`.
- Added CLI wiring for `local26 diag --project/--hosts/--diag-type/--pid/--duration/--remote-cmd/--out-dir/--ssh-user/--include-disabled/--dry-run` in `src/local26/cli.py` and updated `bin/local26` to dispatch `diag` through the Python entrypoint.
- Added unit coverage in `tests/test_python_diag.py` for project host resolution, disabled-host rejection, diag command rendering, dry-run manifest generation, ssh subprocess invocation, required-argument failure, and parser flags.
- Verified parity with the existing shell test: `bash tests/test_diag.sh`.
- Ollama note: the endpoint at `http://192.168.1.206:11434` is reachable, but `deepseek-r1:7b` was not present in `/api/tags` during this run, so implementation was completed via repo inspection and local test validation.

- 2026-04-23: Migrated the next missing Python CLI handler, `pull-logs`, from the shell wrapper into `src/local26/commands/pull_logs.py`.
- Added CLI wiring for `local26 pull-logs --settings/--hosts/--dest/--jboss-path/--apache-path/--engin-path/--smartxfr-path` in `src/local26/cli.py` and updated `bin/local26` to dispatch `pull-logs` through the Python entrypoint.
- Added unit coverage in `tests/test_python_pull_logs.py` for settings parsing, settings-driven scp invocation, CLI override behavior, missing-path failure handling, and parser flags.
- Verified parity with the existing shell test: `bash tests/test_pull_logs.sh`, and re-ran `pytest -q tests/test_python_pull_logs.py tests/test_python_pull.py`.
- Ollama note: the endpoint at `http://192.168.1.206:11434` is reachable, but the exact requested model name `deepseek-r1:7b` is still absent from `/api/tags` (closest match available: `deepseek-r1:7b-qwen-distill-q4_K_M`), so implementation was completed via repo inspection and local test validation.

- 2026-04-25: The next backlog item was already implemented in Python, so I focused on the missing `plan --summary` integration coverage and restored the documented summary contract in `src/local26/commands/plan.py`.
- Updated `_render_summary()` to emit one compact line per step in the documented `step_id | type | timeout | status` format, with `pending` status for newly generated plans.
- Added unit coverage in `tests/test_python_plan.py` for summary line formatting, `--ci` behavior that skips writing plan files, and parser support for `plan --summary --scope`.
- Verified both existing shell parity tests pass with the Python path: `bash tests/test_plan.sh` and `bash tests/test_plan_summary.sh`, plus `PYTHONPATH=src pytest -q tests/test_python_plan.py`.
- Ollama note: the endpoint at `http://192.168.1.206:11434` is reachable, but `deepseek-r1:7b` still does not appear in `/api/tags`, so I validated this pass via direct repo inspection and local test execution.

- 2026-04-27: The next backlog endpoint, `diff`, was already implemented in Python, so I focused on the missing integration coverage and completed the shell entrypoint wiring.
- Updated `bin/local26` usage and Python dispatch so `local26 diff PLAN_A PLAN_B` now resolves through the Python CLI like the other migrated commands.
- Added unit coverage in `tests/test_python_diff.py` for identical plans, metadata/scope/step change reporting, load-failure handling, `run_diff()` stdout behavior, and CLI parser support.
- Verified with `PYTHONPATH=src pytest -q tests/test_python_diff.py` and a `./bin/local26 diff <planA> <planB>` smoke test.
- Ollama note: the endpoint at `http://192.168.1.206:11434` is reachable, but the exact requested model name `deepseek-r1:7b` is still absent from `/api/tags` (available deepseek variant: `deepseek-r1:7b-qwen-distill-q4_K_M`), so this pass was validated via direct repo inspection and local execution.

- 2026-04-28: The next backlog endpoint pair, `history` and `logs`, already existed in Python but were still missing shell-wrapper integration coverage and command reference updates, so I completed the compatibility wiring and test pass instead of re-implementing them.
- Updated `bin/local26` usage and Python dispatch so `local26 history`, `local26 logs`, `local26 hooks`, `local26 profiles`, and `local26 profile create` resolve through the Python CLI consistently.
- Added dispatch unit coverage in `tests/test_python_cli_dispatch.py` and wrapper coverage in `tests/test_history_logs.sh` for history listing, log rendering, limit handling, and prefix run-id resolution.
- Refreshed operator docs in `docs/commands.md` and `README.md` to surface the newly wired commands.
- Ollama note: a direct `curl` to `http://192.168.1.206:11434/api/tags` returned no JSON payload during this run, so I completed this pass via repo inspection and local test validation.

- 2026-04-29: The next backlog surface (`hooks`, `profiles`, and `profile create`) was already implemented in Python, so I filled the remaining shell-wrapper integration gap instead of re-implementing handlers.
- Added `tests/test_hooks_profiles.sh` to verify `bin/local26` dispatch for profile scaffolding, duplicate-profile failure handling, profile listing, and hook status rendering.
- Verified with `bash tests/test_hooks_profiles.sh` plus `PYTHONPATH=src pytest -q tests/test_python_cli_dispatch.py tests/test_python_hooks_profiles_notifications.py`.
- Ollama note: `http://192.168.1.206:11434/api/tags` is reachable, but the exact requested model `deepseek-r1:7b` is still unavailable there; `/api/generate` for that model returned HTTP 404, so this pass was validated via repo inspection and local test execution.

- 2026-04-30: The next backlog item, guided `init`, was already implemented in Python, so I focused on the missing shell-wrapper integration coverage and help text instead of re-implementing the handler.
- Added `tests/test_init_guided.sh` to verify `bin/local26 help` advertises `init --guided` and that the interactive guided flow writes a usable `.local26/config.ini` plus initial state through the shell entrypoint.
- Added CLI dispatch coverage in `tests/test_python_cli_dispatch.py` for `local26 init --guided --force` so the Python path stays pinned during future wrapper migrations.
- Verified with `bash tests/test_init_guided.sh` and `PYTHONPATH=src pytest -q tests/test_python_cli_dispatch.py tests/test_python_guided.py`.
- Ollama note: `http://192.168.1.206:11434/api/tags` is reachable, but the exact requested model `deepseek-r1:7b` is still unavailable there; `/api/generate` for that model returned HTTP 404, so this pass was validated via repo inspection and local test execution.

- 2026-05-01: The next unimplemented deploy surface was `local26 deploy --latest`, and the Python deploy path still had shell-parity gaps around run artifacts and `remote_cmd` host execution.
- Added `--latest` parser/handler support so deploy/check can resolve the newest `.local26/plans/*.plan.json` without an explicit `--plan` path.
- Restored deploy wrapper compatibility by writing `run.log`, suppressing scope-state writes on failed live deploys, and executing `remote_cmd` steps over `ssh` using the plan's `server`/host target.
- Added unit coverage in `tests/test_python_deploy.py` for latest-plan resolution, `--latest` parser support, run-log creation, failed-deploy state behavior, and remote command host dispatch; added shell coverage in `tests/test_deploy.sh` for `deploy --latest`.
- Verified with `PYTHONPATH=src pytest -q tests/test_python_deploy.py tests/test_python_cli_dispatch.py` and `bash tests/test_deploy.sh`.
- Ollama note: `http://192.168.1.206:11434` is reachable, `deepseek-r1:7b` is now present in `/api/tags`, and `/api/generate` returned successfully during this pass.
