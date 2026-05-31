#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "${tmpdir}/modern.ini" <<'CFG'
[local26]
version = 0.1
project = fixture

[tools]
ssh = /usr/bin/ssh

[scope "web"]
enabled = true
source_dir = /srv/web
target_dir = /opt/web
servers = web1

[scope "api"]
enabled = true
source_dir = /srv/api
target_dir = /opt/api
servers = api1
CFG

mkdir -p "${tmpdir}/state"
touch -d '2024-06-01 01:02:03 UTC' "${tmpdir}/state/web.last"

(
  cd "$tmpdir"
  "$repo_root/bin/local26" init --force --import "${tmpdir}/modern.ini"
)

test -f "${tmpdir}/.local26/config.ini"
cmp -s "${tmpdir}/modern.ini" "${tmpdir}/.local26/config.ini"

test -f "${tmpdir}/.local26/state/web.json"
test -f "${tmpdir}/.local26/state/api.json"
grep -Eq '"last_success"[[:space:]]*:[[:space:]]*"2024-06-01T01:02:03Z"' "${tmpdir}/.local26/state/web.json"
grep -Eq '"last_success"[[:space:]]*:[[:space:]]*null' "${tmpdir}/.local26/state/api.json"

echo "test_init_modern.sh: ok"
