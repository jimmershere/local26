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

[api]
source_dir=/srv/api-src
target_dir=/srv/api-dst
servers=api1 api2

[web]
source_dir=/ignored
target_dir=/ignored
servers=ignored1,ignored2
CFG

mkdir -p "${tmpdir}/state"
touch -d '2024-02-03 04:05:06 UTC' "${tmpdir}/state/web.last"

(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --force --project demo >/tmp/seraf-test-out.txt
)

test -f "${tmpdir}/.seraf/config.ini"
rg -q '^default_scope = web$' "${tmpdir}/.seraf/config.ini"
rg -q '^\[scope "web"\]' "${tmpdir}/.seraf/config.ini"
rg -q '^\[scope "api"\]' "${tmpdir}/.seraf/config.ini"
rg -q '^servers = app1,app2,app3$' "${tmpdir}/.seraf/config.ini"

web_line="$(rg -n '^\[scope "web"\]' "${tmpdir}/.seraf/config.ini" | cut -d: -f1)"
api_line="$(rg -n '^\[scope "api"\]' "${tmpdir}/.seraf/config.ini" | cut -d: -f1)"
if [ "$web_line" -ge "$api_line" ]; then
  echo "expected web scope before api scope" >&2
  exit 1
fi

if rg -q '^source_dir = /ignored$' "${tmpdir}/.seraf/config.ini"; then
  echo "duplicate scope should keep first declaration" >&2
  exit 1
fi

test -f "${tmpdir}/.seraf/state/web.json"
test -f "${tmpdir}/.seraf/state/api.json"
rg -q '"last_success":"2024-02-03T04:05:06Z"' "${tmpdir}/.seraf/state/web.json"
rg -q '"last_success":null' "${tmpdir}/.seraf/state/api.json"

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init >/tmp/seraf-test-out-2.txt 2>/tmp/seraf-test-err-2.txt
)
second_rc=$?
set -e

if [ "$second_rc" -eq 0 ]; then
  echo "expected init without --force to fail" >&2
  exit 1
fi

rg -q 'already exists; rerun with --force' /tmp/seraf-test-err-2.txt

missing_tmpdir="$(mktemp -d)"
set +e
(
  cd "$missing_tmpdir"
  "$repo_root/bin/seraf" init >/tmp/seraf-test-out-3.txt 2>/tmp/seraf-test-err-3.txt
)
missing_rc=$?
set -e
rm -rf "$missing_tmpdir"

if [ "$missing_rc" -eq 0 ]; then
  echo "expected init without --import and without settings.cfg to fail" >&2
  exit 1
fi

rg -q 'no legacy config provided and \./settings.cfg not found' /tmp/seraf-test-err-3.txt

echo "test_init.sh: ok"
