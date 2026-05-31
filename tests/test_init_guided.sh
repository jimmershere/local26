#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

help_out="$(mktemp "${tmpdir}/help.XXXXXX")"
(
  cd "$tmpdir"
  "$repo_root/bin/local26" help >"$help_out"
)

grep -q 'local26 init \[--import PATH\] \[--force\] \[--project NAME\] \[--guided\]' "$help_out"

guided_out="$(mktemp "${tmpdir}/guided-out.XXXXXX")"
(
  cd "$tmpdir"
  printf 'demo\nweb\n./src\ny\n/opt/demo\ny\napp1 app2\n\ny\ny\n\n2\nn\nwrite\n' | "$repo_root/bin/local26" init --guided >"$guided_out"
)

test -f "${tmpdir}/.local26/config.ini"
test -f "${tmpdir}/.local26/config.yaml"
grep -q '^project = demo$' "${tmpdir}/.local26/config.ini"
grep -q '^default_scope = web$' "${tmpdir}/.local26/config.ini"
grep -q '^source_dir = ./src$' "${tmpdir}/.local26/config.ini"
grep -q '^target_dir = /opt/demo$' "${tmpdir}/.local26/config.ini"
grep -q '^servers = app1,app2$' "${tmpdir}/.local26/config.ini"
grep -q '^max_parallel = 2$' "${tmpdir}/.local26/config.ini"

test -f "${tmpdir}/.local26/state/web.json"
grep -q '"scope":"web"' "${tmpdir}/.local26/state/web.json"
grep -q "Next good steps: run 'local26 doctor', then 'local26 plan --summary'." "$guided_out"

echo "test_init_guided.sh: ok"
