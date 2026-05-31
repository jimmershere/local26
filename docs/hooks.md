# Local-26 hooks

Local-26 looks for optional shell hooks in `.local26/hooks/`.

## Supported hooks

- `pre-deploy.sh`
- `post-deploy.sh`

## Behavior

- If `pre-deploy.sh` exists, Local-26 runs it before any deploy steps.
- A non-zero `pre-deploy.sh` exit code aborts the deploy.
- If `post-deploy.sh` exists, Local-26 runs it after the deploy finishes.
- A non-zero `post-deploy.sh` exit code is logged as a warning and does not fail the deploy.

## Environment

Local-26 exports:

- `LOCAL26_PLAN`
- `LOCAL26_RUN_ID`
- `LOCAL26_PROFILE`
- `LOCAL26_DEPLOY_RC` (post hook only)

## Listing hooks

```bash
local26 hooks
```

## Example

```bash
mkdir -p .local26/hooks
cat > .local26/hooks/pre-deploy.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "preflight checks"
EOF
chmod +x .local26/hooks/pre-deploy.sh
```
