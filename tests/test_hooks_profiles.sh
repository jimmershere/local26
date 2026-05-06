#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# profile create + profiles list render through the shell wrapper
(
  cd "$tmpdir"

  out="$($repo_root/bin/seraf profile create prod 2>&1)"
  printf '%s\n' "$out" | grep -q "Created profile:" || { printf 'FAIL: missing create confirmation\n'; exit 1; }
  test -f .seraf/profiles/prod.yaml || { printf 'FAIL: profile file was not created\n'; exit 1; }

  out="$($repo_root/bin/seraf profiles 2>&1)"
  printf '%s\n' "$out" | grep -q "Seraf profiles" || { printf 'FAIL: missing profiles header\n'; exit 1; }
  printf '%s\n' "$out" | grep -q '^prod$' || { printf 'FAIL: missing created profile in listing\n'; exit 1; }

  duplicate_out="$tmpdir/profile-duplicate.out"
  if "$repo_root/bin/seraf" profile create prod >"$duplicate_out" 2>&1; then
    printf 'FAIL: duplicate profile create should fail\n'
    exit 1
  fi
  grep -q "Profile already exists:" "$duplicate_out" || { printf 'FAIL: missing duplicate profile message\n'; exit 1; }
)

# hooks renders installed/missing states through the shell wrapper
(
  cd "$tmpdir"
  mkdir -p .seraf/hooks
  cat > .seraf/hooks/pre-deploy.sh <<'HOOK'
#!/usr/bin/env bash
exit 0
HOOK
  chmod +x .seraf/hooks/pre-deploy.sh

  out="$($repo_root/bin/seraf hooks 2>&1)"
  printf '%s\n' "$out" | grep -q "Seraf hooks" || { printf 'FAIL: missing hooks header\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "pre-deploy.sh: installed" || { printf 'FAIL: missing installed hook state\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "post-deploy.sh: missing" || { printf 'FAIL: missing absent hook state\n'; exit 1; }
)

echo "test_hooks_profiles.sh: ok"
