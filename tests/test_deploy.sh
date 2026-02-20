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
  python3 - <<'PY' "$dir/.seraf/plans/test.plan.json" "$fp"
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
if [ "${SERAF_PIPE_OUTPUT:-0}" = "1" ]; then
  printf 'out|pipe\n'
  printf 'err|pipe\n' >&2
fi
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

assert_pipe_output_preserved() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    SERAF_PIPE_OUTPUT=1 PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web --max-parallel 1 >"$tmpdir/out.txt"
  )

  run_dir="$(ls -1 "$tmpdir/.seraf/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.seraf/runs/$run_dir/run.json"
import json,sys
run=json.load(open(sys.argv[1]))
rsync=[s for s in run["steps"] if s["type"]=="rsync"]
assert rsync, run
assert rsync[0]["stdout"] == "out|pipe", rsync[0]
assert rsync[0]["stderr"] == "err|pipe", rsync[0]
PY
}

test_parallel_race_runjson_integrity() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  python3 - <<'PY' "$tmpdir/.seraf/plans/test.plan.json"
import json,sys
path=sys.argv[1]
with open(path, encoding="utf-8") as f:
    plan=json.load(f)
plan["scopes"][0]["steps"]=[
    {
      "id":f"scope:web:{i:04d}",
      "type":"rsync",
      "host":"h1",
      "cmd":f'rsync -az -- "/tmp/src-{i}" "h1:/srv/app/dst-{i}"'
    }
    for i in range(1,51)
]
with open(path,"w",encoding="utf-8") as f:
    json.dump(plan,f,separators=(",",":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
jitter_pre_ms=$((RANDOM % 201))
sleep "0.$(printf '%03d' "$jitter_pre_ms")"
printf 'rsync %s\n' "$*" >> "${SERAF_STUB_LOG}"
jitter_post_ms=$((RANDOM % 201))
sleep "0.$(printf '%03d' "$jitter_post_ms")"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  set +e
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" timeout -k 5 90 "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web --max-parallel 10 >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )
  deploy_rc=$?
  set -e
  [ "$deploy_rc" -eq 0 ] || { echo "parallel deploy failed rc=$deploy_rc"; cat "$tmpdir/err.txt"; return 1; }

  run_dir="$(ls -1 "$tmpdir/.seraf/runs" | sort | tail -n1)"
  run_json_path="$tmpdir/.seraf/runs/$run_dir/run.json"
  [ -f "$run_json_path" ]

  python3 - <<'PY' "$run_json_path"
import json,re,sys
from collections import Counter
run_json_path=sys.argv[1]

try:
    with open(run_json_path, encoding="utf-8") as f:
        run=json.load(f)
except Exception as e:
    raise AssertionError(f"run.json parse failed: {e}")

steps=run.get("steps")
if not isinstance(steps, list):
    raise AssertionError(f"run.steps must be a list, got: {type(steps).__name__}")

step_count=len(steps)
ids=[s.get("id") for s in steps]
counts=Counter(ids)
dupes=sorted([sid for sid,c in counts.items() if c > 1])

if step_count != 50:
    raise AssertionError(
        f"run step count mismatch: detected_count={step_count}, duplicate_ids={dupes}"
    )

missing_required=[]
for i,s in enumerate(steps):
    required=("scope","id","type","host","cmd","started_at","finished_at","rc","stdout","stderr")
    missing=[k for k in required if k not in s]
    if missing:
        missing_required.append((i,missing))
if missing_required:
    raise AssertionError(f"steps missing required fields: {missing_required[:5]}")

pattern=re.compile(r"^scope:web:(\d{4})$")
parsed=[]
for sid in ids:
    if not isinstance(sid, str):
        raise AssertionError(f"step id must be a string, got: {sid!r}")
    m=pattern.match(sid)
    if not m:
        raise AssertionError(f"unexpected step id format: {sid}")
    parsed.append(int(m.group(1)))

expected=set(range(1,51))
actual=set(parsed)
if actual != expected:
    missing=sorted(expected-actual)
    extra=sorted(actual-expected)
    raise AssertionError(f"step id coverage mismatch: missing={missing}, extra={extra}, duplicate_ids={dupes}")

non_terminal=[(s.get("id"), s.get("rc")) for s in steps if not isinstance(s.get("rc"), int)]
if non_terminal:
    raise AssertionError(f"steps with non-terminal rc values: {non_terminal[:5]}")

failures=[(s.get("id"), s.get("rc")) for s in steps if s.get("rc") != 0]
if failures:
    raise AssertionError(f"expected all steps to succeed, failures={failures[:5]}")

if run.get("rc") != 0:
    raise AssertionError(f"run-level rc must be 0, got: {run.get('rc')}")

for s in steps:
    started=s.get("started_at")
    finished=s.get("finished_at")
    if started and finished and started > finished:
        raise AssertionError(
            f"invalid timestamps for {s.get('id')}: started_at={started}, finished_at={finished}"
        )
PY
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
  python3 - <<'PY' "$SERAF_STUB_LOG"
import sys
lines=[l.strip() for l in open(sys.argv[1]) if l.strip()]
assert lines[0].startswith("ssh "), lines
assert lines[1].startswith("rsync "), lines
assert lines[2].startswith("rsync "), lines
PY

  run_dir="$(ls -1 "$tmpdir/.seraf/runs" | sort | tail -n1)"
  [ -f "$tmpdir/.seraf/runs/$run_dir/run.json" ]
  [ -f "$tmpdir/.seraf/runs/$run_dir/run.log" ]

  python3 - <<'PY' "$tmpdir/.seraf/runs/$run_dir/run.json" "$tmpdir/.seraf/state/web.json"
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


assert_remote_cmd_barrier_ordering() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  python3 - <<'PY2' "$tmpdir/.seraf/plans/test.plan.json"
import json,sys
path=sys.argv[1]
with open(path, encoding="utf-8") as f:
    plan=json.load(f)
plan["scopes"][0]["steps"]=[
  {"id":"scope:web:0001","type":"rsync","host":"h1","cmd":"rsync -az -- \"/tmp/a\" \"h1:/srv/app/a\""},
  {"id":"scope:web:0002","type":"rsync","host":"h1","cmd":"rsync -az -- \"/tmp/b\" \"h1:/srv/app/b\""},
  {"id":"scope:web:0003","type":"remote_cmd","server":"h1","cmd":"systemctl stop app","label":"stop"},
  {"id":"scope:web:0004","type":"rsync","host":"h1","cmd":"rsync -az -- \"/tmp/c\" \"h1:/srv/app/c\""}
]
with open(path,"w",encoding="utf-8") as f:
    json.dump(plan,f,separators=(",",":"))
PY2

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *"/tmp/c"* ]]; then
  tag="c"
else
  sleep 0.2
  if [[ "$*" == *"/tmp/a"* ]]; then
    tag="a"
  else
    tag="b"
  fi
fi
printf 'rsync-start:%s\n' "$tag" >> "${SERAF_STUB_LOG}"
if [ "$tag" != "c" ]; then
  sleep 0.2
fi
printf 'rsync-end:%s\n' "$tag" >> "${SERAF_STUB_LOG}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  cat > "$tmpdir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh:%s\n' "$*" >> "${SERAF_STUB_LOG}"
SSH
  chmod +x "$tmpdir/stubs/ssh"

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web --max-parallel 2 >"$tmpdir/out.txt"
  )

  python3 - <<'PY2' "$SERAF_STUB_LOG"
import sys
lines=[l.strip() for l in open(sys.argv[1]) if l.strip()]
remote_idx=next(i for i,l in enumerate(lines) if l.startswith("ssh:h1 systemctl stop app"))
a_end=next(i for i,l in enumerate(lines) if l=="rsync-end:a")
b_end=next(i for i,l in enumerate(lines) if l=="rsync-end:b")
c_start=next(i for i,l in enumerate(lines) if l=="rsync-start:c")
assert a_end < remote_idx, lines
assert b_end < remote_idx, lines
assert remote_idx < c_start, lines
PY2
}

assert_zero_step_scope_updates_state() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  python3 - <<'PY' "$tmpdir/.seraf/plans/test.plan.json"
import json,sys
path=sys.argv[1]
with open(path) as f:
    plan=json.load(f)
plan["scopes"][0]["steps"]=[]
with open(path,"w") as f:
    json.dump(plan,f,separators=(",",":"))
PY

  export SERAF_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/seraf" deploy --plan "$tmpdir/.seraf/plans/test.plan.json" --scope web >"$tmpdir/out.txt"
  )

  run_dir="$(ls -1 "$tmpdir/.seraf/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.seraf/runs/$run_dir/run.json" "$tmpdir/.seraf/state/web.json"
import json,sys
run=json.load(open(sys.argv[1]))
assert run["rc"] == 0
assert run["steps"] == []
state=json.load(open(sys.argv[2]))
assert state["last_plan_id"] == "p1"
assert state["last_run_id"] == run["run_id"]
assert state["files_last_deployed_count"] == 0
assert state["last_success"]
PY
}

assert_success_case
assert_failure_case
assert_zero_step_scope_updates_state
assert_pipe_output_preserved
test_parallel_race_runjson_integrity
assert_remote_cmd_barrier_ordering

echo "test_deploy.sh: ok"
