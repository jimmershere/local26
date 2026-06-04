#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "${tmpdir}/settings.cfg" <<'CFG'
[web]
source_dir = /srv/source
 target_dir=/srv/target
servers = app1, app2 ,app3
rsync_opts = -az --delete
backup = TRue

[api]
source_dir=/srv/api-src
target_dir=/srv/api-dst
servers=api1 api2
backup=maybe

[web]
source_dir=/ignored
target_dir=/ignored
servers=ignored1,ignored2
CFG

mkdir -p "${tmpdir}/state"
touch -d '2024-02-03 04:05:06 UTC' "${tmpdir}/state/web.last"

init_out="$(mktemp "${tmpdir}/local81-test-out.XXXXXX")"
init_err="$(mktemp "${tmpdir}/local81-test-err.XXXXXX")"

(
  cd "$tmpdir"
  "$repo_root/bin/local81" init --force --project demo >"$init_out" 2>"$init_err"
)

test -f "${tmpdir}/.local81/config.ini"
grep -q '^default_scope = web$' "${tmpdir}/.local81/config.ini"
grep -q '^\[scope "web"\]' "${tmpdir}/.local81/config.ini"
grep -q '^\[scope "api"\]' "${tmpdir}/.local81/config.ini"
grep -q '^servers = app1,app2,app3$' "${tmpdir}/.local81/config.ini"
grep -q '^backup = true$' "${tmpdir}/.local81/config.ini"
grep -q "legacy section \[api\] has invalid backup value 'maybe'; expected true/false, ignoring" "$init_err"

web_line="$(grep -n '^\[scope "web"\]' "${tmpdir}/.local81/config.ini" | cut -d: -f1)"
api_line="$(grep -n '^\[scope "api"\]' "${tmpdir}/.local81/config.ini" | cut -d: -f1)"
if [ "$web_line" -ge "$api_line" ]; then
  echo "expected web scope before api scope" >&2
  exit 1
fi

if grep -q '^source_dir = /ignored$' "${tmpdir}/.local81/config.ini"; then
  echo "duplicate scope should keep first declaration" >&2
  exit 1
fi

api_scope_block="$(sed -n '/^\[scope "api"\]/,/^\[scope "/p' "${tmpdir}/.local81/config.ini")"
if printf '%s\n' "$api_scope_block" | grep -q '^backup = '; then
  echo "api scope should not include invalid legacy backup value" >&2
  exit 1
fi

test -f "${tmpdir}/.local81/state/web.json"
test -f "${tmpdir}/.local81/state/api.json"
grep -Eq '"last_success"[[:space:]]*:[[:space:]]*"2024-02-03T04:05:06Z"' "${tmpdir}/.local81/state/web.json"
grep -Eq '"last_success"[[:space:]]*:[[:space:]]*null' "${tmpdir}/.local81/state/api.json"

second_out="$(mktemp "${tmpdir}/local81-test-out-2.XXXXXX")"
second_err="$(mktemp "${tmpdir}/local81-test-err-2.XXXXXX")"

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local81" init >"$second_out" 2>"$second_err"
)
second_rc=$?
set -e

if [ "$second_rc" -eq 0 ]; then
  echo "expected init without --force to fail" >&2
  exit 1
fi

grep -q 'already exists; rerun with --force' "$second_err"

missing_tmpdir="$(mktemp -d)"
missing_out="$(mktemp "${missing_tmpdir}/local81-test-out-3.XXXXXX")"
missing_err="$(mktemp "${missing_tmpdir}/local81-test-err-3.XXXXXX")"
set +e
(
  cd "$missing_tmpdir"
  "$repo_root/bin/local81" init >"$missing_out" 2>"$missing_err"
)
missing_rc=$?
set -e

if [ "$missing_rc" -eq 0 ]; then
  echo "expected init without --import and without settings.cfg to fail" >&2
  exit 1
fi

grep -q 'no legacy config provided and \./settings.cfg not found' "$missing_err"

rm -rf "$missing_tmpdir"

echo "test_init.sh: ok"
