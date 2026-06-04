# Local-81 hooks

Local-81 looks for optional shell hooks in `.local81/hooks/`.

## Supported hooks

- `pre-deploy.sh`
- `post-deploy.sh`

## Behavior

- If `pre-deploy.sh` exists, Local-81 runs it before any deploy steps.
- A non-zero `pre-deploy.sh` exit code aborts the deploy.
- If `post-deploy.sh` exists, Local-81 runs it after the deploy finishes.
- A non-zero `post-deploy.sh` exit code is logged as a warning and does not fail the deploy.

## Environment

Local-81 exports:

- `LOCAL81_PLAN`
- `LOCAL81_RUN_ID`
- `LOCAL81_PROFILE`
- `LOCAL81_DEPLOY_RC` (post hook only)

## Listing hooks

```bash
local81 hooks
```

## Example

```bash
mkdir -p .local81/hooks
cat > .local81/hooks/pre-deploy.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "preflight checks"
EOF
chmod +x .local81/hooks/pre-deploy.sh
```
