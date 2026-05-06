#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

help_out="$(mktemp "${tmpdir}/help.XXXXXX")"
(
  cd "$tmpdir"
  "$repo_root/bin/seraf" help >"$help_out"
)

grep -q 'seraf init \[--import PATH\] \[--force\] \[--project NAME\] \[--guided\]' "$help_out"

guided_out="$(mktemp "${tmpdir}/guided-out.XXXXXX")"
(
  cd "$tmpdir"
  printf 'demo\nweb\n./src\ny\n/opt/demo\ny\napp1 app2\n\ny\ny\n\n2\nn\nwrite\n' | "$repo_root/bin/seraf" init --guided >"$guided_out"
)

test -f "${tmpdir}/.seraf/config.ini"
test -f "${tmpdir}/.seraf/config.yaml"
grep -q '^project = demo$' "${tmpdir}/.seraf/config.ini"
grep -q '^default_scope = web$' "${tmpdir}/.seraf/config.ini"
grep -q '^source_dir = ./src$' "${tmpdir}/.seraf/config.ini"
grep -q '^target_dir = /opt/demo$' "${tmpdir}/.seraf/config.ini"
grep -q '^servers = app1,app2$' "${tmpdir}/.seraf/config.ini"
grep -q '^max_parallel = 2$' "${tmpdir}/.seraf/config.ini"

test -f "${tmpdir}/.seraf/state/web.json"
grep -q '"scope":"web"' "${tmpdir}/.seraf/state/web.json"
grep -q "Next good steps: run 'seraf doctor', then 'seraf plan --summary'." "$guided_out"

echo "test_init_guided.sh: ok"
