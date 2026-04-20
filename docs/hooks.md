# Seraf hooks

Seraf looks for optional shell hooks in `.seraf/hooks/`.

## Supported hooks

- `pre-deploy.sh`
- `post-deploy.sh`

## Behavior

- If `pre-deploy.sh` exists, Seraf runs it before any deploy steps.
- A non-zero `pre-deploy.sh` exit code aborts the deploy.
- If `post-deploy.sh` exists, Seraf runs it after the deploy finishes.
- A non-zero `post-deploy.sh` exit code is logged as a warning and does not fail the deploy.

## Environment

Seraf exports:

- `SERAF_PLAN`
- `SERAF_RUN_ID`
- `SERAF_PROFILE`
- `SERAF_DEPLOY_RC` (post hook only)

## Listing hooks

```bash
seraf hooks
```

## Example

```bash
mkdir -p .seraf/hooks
cat > .seraf/hooks/pre-deploy.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "preflight checks"
EOF
chmod +x .seraf/hooks/pre-deploy.sh
```
