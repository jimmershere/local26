#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

write_valid_config() {
  local path="$1"
  cat > "$path" <<'CFG'
[local26]
version = 0.1
project = validation-test
default_scope = web
state_dir = .local26/state
plans_dir = .local26/plans
runs_dir = .local26/runs
logs_dir = .local26/logs
lock_file = .local26/local26.lock
require_plan_for_deploy = true
fail_fast = true
max_parallel = 4
shell = /usr/bin/bash

[tools]
ssh = /usr/bin/ssh
rsync = /usr/bin/rsync
find = /usr/bin/find

[defaults]
rsync_opts = -az
backup = true
backup_suffix = .bkp
remote_mkdir = true
dry_run_default = false
log_hosts =
log_dest_dir = .local26/pulled-logs
jboss_log_path =
apache_log_path =
engin_log_path =
smartxfr_log_path =

[routing]
env_from_filename_prefix = s:sys,q:qa,p:production
env_from_server_name_char_at = 4
env_from_server_name_char_map = s:sys,q:qa,p:production

[access]
allowed_users =
allowed_groups =
denied_users =
deny_root = false
allow_remote_cmd = false

[scope "web"]
enabled = true
source_dir = /srv/source
target_dir = /srv/target
servers = app1,app2
discovery = mtime_since_last_success
CFG
}

write_plan() {
  local path="$1"
  cat > "$path" <<'JSON'
{
  "schema": "local26.plan.v0.1",
  "kind": "plan",
  "mode": "deploy",
  "plan_id": "config-validation",
  "scopes": [
    {
      "scope": "web",
      "steps": [
        {
          "id": "scope:web:0001",
          "type": "rsync",
          "host": "app1",
          "cmd": "rsync -az -- \"/tmp/a\" \"app1:/srv/target/a\""
        }
      ]
    }
  ]
}
JSON
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/.local26/plans" "$tmpdir/.local26/runs" "$tmpdir/.local26/state"
write_valid_config "$tmpdir/.local26/config.ini"
write_plan "$tmpdir/.local26/plans/valid.plan.json"

(
  cd "$tmpdir"
  "$repo_root/bin/local26" doctor >"$tmpdir/doctor-valid.out"
)
grep -q '\[PASS\] config:schema:' "$tmpdir/doctor-valid.out"

(
  cd "$tmpdir"
  "$repo_root/bin/local26" deploy --plan "$tmpdir/.local26/plans/valid.plan.json" --check >"$tmpdir/check-valid.out"
)
grep -q 'Check passed' "$tmpdir/check-valid.out"

cp "$tmpdir/.local26/config.ini" "$tmpdir/.local26/config.ini.good"
python3 - <<'PY' "$tmpdir/.local26/config.ini"
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text = text.replace("project = validation-test", "project = validation-test\nunknown_key = nope")
open(path, "w", encoding="utf-8").write(text)
PY

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local26" doctor >"$tmpdir/doctor-bad-key.out" 2>"$tmpdir/doctor-bad-key.err"
)
bad_doctor_rc=$?
set -e
[ "$bad_doctor_rc" -ne 0 ]
grep -q 'unknown key \[local26\] unknown_key' "$tmpdir/doctor-bad-key.out"

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local26" deploy --plan "$tmpdir/.local26/plans/valid.plan.json" --check >"$tmpdir/check-bad-key.out" 2>"$tmpdir/check-bad-key.err"
)
bad_check_rc=$?
set -e
[ "$bad_check_rc" -ne 0 ]
grep -q 'unknown key \[local26\] unknown_key' "$tmpdir/check-bad-key.out"

mv "$tmpdir/.local26/config.ini.good" "$tmpdir/.local26/config.ini"
cat >> "$tmpdir/.local26/config.ini" <<'CFG'

[scope "web"]
enabled = true
source_dir = /dup
target_dir = /dup
servers = dup
discovery = mtime_since_last_success
CFG

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local26" doctor >"$tmpdir/doctor-duplicate.out" 2>"$tmpdir/doctor-duplicate.err"
)
duplicate_rc=$?
set -e
[ "$duplicate_rc" -ne 0 ]
grep -q 'could not parse' "$tmpdir/doctor-duplicate.out"

write_valid_config "$tmpdir/.local26/config.ini"
cat >> "$tmpdir/.local26/config.ini" <<'CFG'

[mystery]
foo = bar
CFG

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local26" doctor >"$tmpdir/doctor-unknown-section.out" 2>"$tmpdir/doctor-unknown-section.err"
)
unknown_section_rc=$?
set -e
[ "$unknown_section_rc" -ne 0 ]
grep -q 'unknown section \[mystery\]' "$tmpdir/doctor-unknown-section.out"

echo "test_config_validation.sh: ok"
