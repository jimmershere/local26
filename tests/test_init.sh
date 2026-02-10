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
CFG

mkdir -p "${tmpdir}/state"
touch -d '2024-02-03 04:05:06 UTC' "${tmpdir}/state/web.last"

(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --import ./settings.cfg --force --project demo >/tmp/seraf-test-out.txt
)

test -f "${tmpdir}/.seraf/config.ini"
rg -q '^\[scope "web"\]' "${tmpdir}/.seraf/config.ini"
rg -q '^\[scope "api"\]' "${tmpdir}/.seraf/config.ini"
rg -q '^servers=app1,app2,app3$' "${tmpdir}/.seraf/config.ini"

test -f "${tmpdir}/.seraf/state/web.json"
test -f "${tmpdir}/.seraf/state/api.json"
rg -q '"last_success":"2024-02-03T04:05:06Z"' "${tmpdir}/.seraf/state/web.json"
rg -q '"last_success":null' "${tmpdir}/.seraf/state/api.json"

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --import ./settings.cfg >/tmp/seraf-test-out-2.txt 2>/tmp/seraf-test-err-2.txt
)
second_rc=$?
set -e

if [ "$second_rc" -eq 0 ]; then
  echo "expected init without --force to fail" >&2
  exit 1
fi

rg -q 'already exists; rerun with --force' /tmp/seraf-test-err-2.txt

echo "test_init.sh: ok"
