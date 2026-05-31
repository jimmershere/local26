#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

mkdir -p "$tmpdir/.local81/plans" "$tmpdir/.local81/runs" "$tmpdir/.local81/state" "$tmpdir/stubs"
cat > "$tmpdir/.local81/config.ini" <<'CFG'
[local81]
version = 0.1
project = policy-test

[access]
allowed_users =
allowed_groups =
denied_users =
deny_root = false
allow_remote_cmd = false

[access.providers]
enabled = ldap,sudo,service_accounts,external
fail_closed = true

[access.ldap]
enabled = true
uri = ldap://ad.example.com

[access.sudo]
enabled = true

[access.service_accounts]
enabled = true

[access.external]
enabled = true
CFG

cat > "$tmpdir/.local81/plans/policy.plan.json" <<'JSON'
{
  "schema": "local81.plan.v0.1",
  "kind": "plan",
  "mode": "deploy",
  "local81_version": "0.1",
  "plan_id": "policy-plan",
  "created_at": "2026-01-01T00:00:00Z",
  "config_fingerprint": "sha256:deadbeef",
  "scopes": [
    {
      "scope": "web",
      "steps": [
        {
          "id": "scope:web:0001",
          "type": "rsync",
          "host": "h1",
          "cmd": "rsync -az -- \"/tmp/a\" \"h1:/srv/app/a\""
        }
      ]
    },
    {
      "scope": "admin",
      "steps": [
        {
          "id": "scope:admin:0001",
          "type": "remote_cmd",
          "server": "h1",
          "cmd": "systemctl restart app"
        }
      ]
    }
  ]
}
JSON

cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync %s\n' "$*" >> "${LOCAL81_STUB_LOG}"
RSYNC
chmod +x "$tmpdir/stubs/rsync"

cat > "$tmpdir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\n' "$*" >> "${LOCAL81_STUB_LOG}"
SSH
chmod +x "$tmpdir/stubs/ssh"

export LOCAL81_STUB_LOG="$tmpdir/calls.log"
(
  cd "$tmpdir"
  PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy --plan "$tmpdir/.local81/plans/policy.plan.json" --scope web >"$tmpdir/web.out"
)

grep -q 'Deploy finished cleanly' "$tmpdir/web.out"
grep -q '^rsync ' "$LOCAL81_STUB_LOG"

run_dir="$(ls -1 "$tmpdir/.local81/runs" | sort | tail -n1)"
[ "$(stat -c '%a' "$tmpdir/.local81/runs/$run_dir")" = "700" ]
[ "$(stat -c '%a' "$tmpdir/.local81/runs/$run_dir/run.json")" = "600" ]
[ "$(stat -c '%a' "$tmpdir/.local81/runs/$run_dir/run.log")" = "600" ]
[ "$(stat -c '%a' "$tmpdir/.local81/state/web.json")" = "600" ]

spoofed_actor="$(LOGNAME=spoofed USER=spoofed PYTHONPATH="$repo_root/src" python3 - <<'PY'
from local81.policy import current_actor
print(current_actor().user)
PY
)"
[ "$spoofed_actor" != "spoofed" ]

set +e
(
  cd "$tmpdir"
  PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy --plan "$tmpdir/.local81/plans/policy.plan.json" --scope admin --check >"$tmpdir/check-admin.out" 2>"$tmpdir/check-admin.err"
)
check_admin_rc=$?
set -e

[ "$check_admin_rc" -ne 0 ]
grep -q 'remote_cmd steps require access.allow_remote_cmd = true' "$tmpdir/check-admin.out"

set +e
(
  cd "$tmpdir"
  PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy --plan "$tmpdir/.local81/plans/policy.plan.json" --scope admin >"$tmpdir/admin.out" 2>"$tmpdir/admin.err"
)
admin_rc=$?
set -e

[ "$admin_rc" -ne 0 ]
grep -q 'Local-81 deploy blocked by access-control policy' "$tmpdir/admin.out"
grep -q 'remote_cmd steps require access.allow_remote_cmd = true' "$tmpdir/admin.out"

(
  cd "$tmpdir"
  "$repo_root/bin/local81" compliance report >"$tmpdir/compliance.out"
)

grep -q 'Local-81 compliance report' "$tmpdir/compliance.out"
grep -q 'CM-5 privileged functions' "$tmpdir/compliance.out"
grep -q 'remote command steps are denied by default' "$tmpdir/compliance.out"
grep -q 'runtime directories and artifacts are owner-only by design' "$tmpdir/compliance.out"
grep -q 'LDAP/AD provider should use ldaps://' "$tmpdir/compliance.out"
grep -q 'LDAP/AD provider is scaffolded only' "$tmpdir/compliance.out"
grep -q 'sudo provider is scaffolded only' "$tmpdir/compliance.out"
grep -q 'service account provider enabled without allowed_accounts' "$tmpdir/compliance.out"
grep -q 'external policy provider enabled without command' "$tmpdir/compliance.out"

cp "$tmpdir/.local81/config.ini" "$tmpdir/.local81/config.ini.good"
python3 - <<'PY' "$tmpdir/.local81/config.ini"
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text = text.replace("deny_root = false", "deny_root = maybe")
open(path, "w", encoding="utf-8").write(text)
PY

set +e
(
  cd "$tmpdir"
  "$repo_root/bin/local81" compliance report >"$tmpdir/compliance-bad.out" 2>"$tmpdir/compliance-bad.err"
)
bad_compliance_rc=$?
set -e

[ "$bad_compliance_rc" -ne 0 ]
grep -q '\[access\] deny_root must be true or false' "$tmpdir/compliance-bad.out"
mv "$tmpdir/.local81/config.ini.good" "$tmpdir/.local81/config.ini"

echo "test_access_policy.sh: ok"
