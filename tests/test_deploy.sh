#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

make_workspace() {
  local dir="$1"
  mkdir -p "$dir/.seraf/state" "$dir/.seraf/plans" "$dir/.seraf/runs" "$dir/stubs"
  cat > "$dir/.seraf/config.ini" <<'CFG'
[seraf]
version = 0.1
CFG

  local fp
  fp="$(sha256sum "$dir/.seraf/config.ini" | awk '{print $1}')"
  python - <<'PY' "$dir/.seraf/plans/test.plan.json" "$fp"
import json,sys
path,fp=sys.argv[1:]
plan={
  "schema":"seraf.plan.v0.1",
  "kind":"plan",
  "mode":"deploy",
  "seraf_version":"0.1",
  "plan_id":"p1",
  "created_at":"2024-01-01T00:00:00Z",
  "config_fingerprint":f"sha256:{fp}",
  "scopes":[{
    "scope":"web",
    "steps":[
      {"id":"scope:web:0001","type":"mkdir","host":"h1","cmd":"ssh \"h1\" \"mkdir -p -- \\\"/srv/app\\\"\""},
      {"id":"scope:web:0002","type":"rsync","host":"h1","cmd":"rsync -az -- \"/tmp/a\" \"h1:/srv/app/a\""},
      {"id":"scope:web:0003","type":"rsync","host":"h1","cmd":"rsync -az -- \"/tmp/b\" \"h1:/srv/app/b\""}
    ],
    "summary":{"counts":{"mkdir_steps":1,"rsync_steps":2,"rollbackable_steps":0,"warnings":[]}}
  }],
  "analysis":{"ai":{"enabled":False}}
}
with open(path,"w",encoding="utf-8") as f:
    json.dump(plan,f,separators=(",",":"))
PY

  cat > "$dir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\n' "$*" >> "${SERAF_STUB_LOG}"
SSH
  chmod +x "$dir/stubs/ssh"

  cat > "$dir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync %s\n' "$*" >> "${SERAF_STUB_LOG}"
if [ "${SERAF_FAIL_SECOND_RSYNC:-0}" = "1" ]; then
  nfile="${SERAF_STUB_LOG}.count"
  n=0
  if [ -f "$nfile" ]; then
    n="$(cat "$nfile")"
  fi
  n=$((n + 1))
  printf '%s' "$n" > "$nfile"
  if [ "$n" -eq 2 ]; then
    exit 9
  fi
fi
RSYNC
  chmod +x "$dir/stubs/rsync"
}

assert_success_case() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web --max-parallel 2 >"$tmpdir/out.txt"
  )

  [ -s "$SERAF_STUB_LOG" ]
  python - <<'PY' "$SERAF_STUB_LOG"
import sys
lines=[l.strip() for l in open(sys.argv[1]) if l.strip()]
assert lines[0].startswith("ssh "), lines
assert lines[1].startswith("rsync "), lines
assert lines[2].startswith("rsync "), lines
PY

  run_dir="$(ls -1 "$tmpdir/.seraf/runs" | head -n1)"
  [ -f "$tmpdir/.seraf/runs/$run_dir/run.json" ]
  [ -f "$tmpdir/.seraf/runs/$run_dir/run.log" ]

  python - <<'PY' "$tmpdir/.seraf/runs/$run_dir/run.json" "$tmpdir/.seraf/state/web.json"
import json,sys
run=json.load(open(sys.argv[1]))
assert run["dry_run"] is False
assert run["rc"]==0
assert [s["id"] for s in run["steps"]]==["scope:web:0001","scope:web:0002","scope:web:0003"]
state=json.load(open(sys.argv[2]))
assert state["last_plan_id"]=="p1"
assert state["files_last_deployed_count"]==2
assert state["last_run_id"]==run["run_id"]
PY
}

assert_failure_case() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  set +e
  (
    cd "$tmpdir"
    SERAF_FAIL_SECOND_RSYNC=1 PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web --max-parallel 1 >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )
  rc=$?
  set -e
  [ "$rc" -ne 0 ]
  [ ! -f "$tmpdir/.seraf/state/web.json" ]
}

assert_success_case
assert_failure_case

echo "test_deploy.sh: ok"
