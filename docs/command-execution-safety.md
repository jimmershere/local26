# Command execution safety
Local-81 currently keeps deployment behavior stable while reducing command execution risk through inventory, diagnostics, and security checks.
## Approved execution paths
The following Python execution paths are known and intentional:
- `src/local81/commands/deploy.py` `_run_shell`: executes plan step `cmd` strings through `bash -lc`. This is the only approved local shell interpreter site because existing plan steps are stored as shell command strings and may include pipes, redirection, rollback snippets, or generated `ssh`/`rsync` commands.
- `src/local81/commands/deploy.py` `_run_remote`: executes `ssh <host> <command>` with argv form for `remote_cmd` steps.
- `src/local81/hooks.py` `run_hook`: executes owner-controlled hook files under `.local81/hooks` with `bash <path>`.
- `src/local81/commands/plan.py` `_git_checkout`: executes `git` with argv form only for configured git workspaces.
- `src/local81/commands/pull.py`, `src/local81/commands/pull_logs.py`, `src/local81/commands/diag.py`, and `src/local81/notifications.py`: execute specific tools with argv form and no `shell=True`.
- `tools/security-check.py` and `tools/format-check.py`: execute `git ls-files` with argv form for repository checks.
## Guardrails
- `tools/security-check.py` fails on `subprocess shell=True`, `os.system`, `os.popen`, and unapproved `["bash", "-lc", ...]` calls.
- `deploy --check` prints execution safety diagnostics for high-risk plan steps, including `remote_cmd`, shell control operators, redirection, `sudo`, rollback commands, and failure handlers. These diagnostics are warnings only and do not change deploy behavior.
- New shell interpreter sites must be documented here and added to `tools/security-check.py` only after review.
## Future runner direction
A deeper runner refactor should preserve the current plan schema but route all execution through a single typed runner interface. The runner should distinguish argv-only execution, explicitly approved shell-string execution, remote SSH execution, dry-run rendering, timeouts, and output capture. Until that migration is designed and tested, deployment behavior should remain unchanged.
