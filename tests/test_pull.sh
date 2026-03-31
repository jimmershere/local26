#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test_pull_dry_run_with_scope_hosts_override() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  mkdir -p "$tmpdir/.seraf"
  cat > "$tmpdir/.seraf/config.ini" <<CFG
[seraf]
version = 0.1

[scope "app"]
enabled = true
source_dir = ${tmpdir}/src/app
target_dir = /srv/app
servers = old1,old2

[scope "api"]
enabled = true
source_dir = ${tmpdir}/src/api
target_dir = /srv/api
servers = api1
CFG

  (
    cd "$tmpdir"
    "$repo_root/bin/seraf" pull --scope app --hosts "m2a,m2b" --dry-run >"$tmpdir/out.txt"
  )

  grep -q '\[pull\] dry-run scope=app host=m2a cmd=rsync -az -- "m2a:/srv/app/" "'${tmpdir}'/src/app/"' "$tmpdir/out.txt"
  grep -q '\[pull\] dry-run scope=app host=m2b cmd=rsync -az -- "m2b:/srv/app/" "'${tmpdir}'/src/app/"' "$tmpdir/out.txt"
  grep -q 'Pulled files into local source dirs (success=2, failed=0)' "$tmpdir/out.txt"
}

test_pull_uses_rsync_stub() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  mkdir -p "$tmpdir/.seraf" "$tmpdir/stubs"
  cat > "$tmpdir/.seraf/config.ini" <<CFG
[seraf]
version = 0.1

[scope "app"]
enabled = true
source_dir = ${tmpdir}/src/app
target_dir = /srv/app
servers = m2host
CFG

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "${SERAF_STUB_LOG}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export SERAF_STUB_LOG="$tmpdir/rsync.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" pull >"$tmpdir/out.txt"
  )

  grep -q 'm2host:/srv/app/' "$tmpdir/rsync.log"
  grep -q "${tmpdir}/src/app/" "$tmpdir/rsync.log"
  grep -q 'Pulled files into local source dirs (success=1, failed=0)' "$tmpdir/out.txt"
}

test_pull_missing_scope_fails() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  mkdir -p "$tmpdir/.seraf"
  cat > "$tmpdir/.seraf/config.ini" <<'CFG'
[seraf]
version = 0.1

[scope "app"]
enabled = true
source_dir = /tmp/src
target_dir = /tmp/remote
servers = h1
CFG

  set +e
  (
    cd "$tmpdir"
    "$repo_root/bin/seraf" pull --scope nope >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )
  local rc=$?
  set -e
  [ "$rc" -ne 0 ]
  grep -q 'no matching scopes found' "$tmpdir/err.txt"
}

test_pull_dry_run_with_scope_hosts_override
test_pull_uses_rsync_stub
test_pull_missing_scope_fails

echo "test_pull.sh: PASS"
