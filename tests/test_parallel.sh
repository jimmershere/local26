#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Tests for parallel:true step flag — steps marked parallel:true run concurrently
# even when they are barrier types (remote_cmd/mkdir).

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

make_workspace() {
  local dir="$1"
  mkdir -p "$dir/.local26/state" "$dir/.local26/plans" "$dir/.local26/runs" "$dir/stubs"
  cat > "$dir/.local26/config.ini" <<'CFG'
[local26]
version = 0.1
CFG
  local fp
  fp="$(sha256sum "$dir/.local26/config.ini" | awk '{print $1}')"
  printf '%s' "$fp"
}

make_plan() {
  local path="$1" fp="$2"
  python3 - <<PY "$path" "$fp"
import json, sys
path, fp = sys.argv[1:]
plan = {
  "schema": "local26.plan.v0.1",
  "kind": "plan",
  "mode": "deploy",
  "local26_version": "0.1",
  "plan_id": "p-par",
  "created_at": "2024-01-01T00:00:00Z",
  "config_fingerprint": f"sha256:{fp}",
  "scopes": [{
    "scope": "web",
    "steps": [],
    "summary": {"counts": {"mkdir_steps": 0, "rsync_steps": 0, "rollbackable_steps": 0, "warnings": []}}
  }],
  "analysis": {"ai": {"enabled": False}}
}
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY
}

# ---------------------------------------------------------------------------
# Test 1: parallel:true on rsync steps runs them truly concurrently
#         Verified by: all steps finish in roughly parallel wall-clock time
#         and all show up in run.json with rc=0.
# ---------------------------------------------------------------------------
test_parallel_flag_concurrent() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  # Overwrite plan with 5 rsync steps each taking 0.3s; with parallel:true and
  # max-parallel 5 the whole run should finish in ~0.3s not 1.5s.
  python3 - <<'PY' "$tmpdir/.local26/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
steps = []
for i in range(1, 6):
    steps.append({
        "id": f"scope:web:{i:04d}",
        "type": "rsync",
        "host": "h1",
        "cmd": f"sleep 0.3 && echo done-{i}",
        "parallel": True
    })
plan["scopes"][0]["steps"] = steps
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  # stub rsync → just runs the cmd via bash
  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
# rsync stub: treat last two args as local/remote — run an approximated sleep
# The cmd is embedded in the plan; the deploy runner calls bash -lc "$cmd"
# so we don't need to do anything special here.
printf 'rsync-stub\n' >> "${LOCAL26_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  # We'll time the deploy
  local t0 t1 elapsed
  t0="$(date +%s%N)"

  export LOCAL26_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" deploy \
      --plan "$tmpdir/.local26/plans/test.plan.json" \
      --scope web --max-parallel 5 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )

  t1="$(date +%s%N)"
  elapsed=$(( (t1 - t0) / 1000000 ))  # ms

  run_dir="$(ls -1 "$tmpdir/.local26/runs" | sort | tail -n1)"
  python3 - <<PY "$tmpdir/.local26/runs/$run_dir/run.json" "$elapsed"
import json, sys
path, elapsed = sys.argv[1], int(sys.argv[2])
run = json.load(open(path))
assert run["rc"] == 0, f"run failed: rc={run['rc']}"
assert len(run["steps"]) == 5, f"expected 5 steps, got {len(run['steps'])}"
failures = [s for s in run["steps"] if s["rc"] != 0]
assert not failures, f"some steps failed: {failures}"
# With 5 parallel steps each sleeping 0.3s, elapsed should be < 1200ms
# (generous headroom for slow CI). Serial would be 1500ms+.
assert elapsed < 1200, f"steps did not appear to run concurrently: elapsed={elapsed}ms"
PY
}

# ---------------------------------------------------------------------------
# Test 2: parallel:true on a barrier type (remote_cmd) — does NOT block earlier
#         rsync steps from dispatching; all complete and results are correct.
# ---------------------------------------------------------------------------
test_parallel_barrier_override() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  python3 - <<'PY' "$tmpdir/.local26/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
plan["scopes"][0]["steps"] = [
    {"id": "scope:web:0001", "type": "rsync", "host": "h1",
     "cmd": "echo rsync-1", "parallel": True},
    # remote_cmd with parallel:true — should NOT block rsync-1 from being in flight
    {"id": "scope:web:0002", "type": "remote_cmd", "host": "h1",
     "cmd": "echo remote-cmd", "parallel": True},
    {"id": "scope:web:0003", "type": "rsync", "host": "h1",
     "cmd": "echo rsync-3", "parallel": True},
]
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  # stubs: ssh and rsync just echo
  cat > "$tmpdir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh-stub %s\n' "$*" >> "${LOCAL26_STUB_LOG:-/dev/null}"
SSH
  chmod +x "$tmpdir/stubs/ssh"

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub %s\n' "$*" >> "${LOCAL26_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL26_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" deploy \
      --plan "$tmpdir/.local26/plans/test.plan.json" \
      --scope web --max-parallel 3 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )

  run_dir="$(ls -1 "$tmpdir/.local26/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local26/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] == 0, f"run failed: rc={run['rc']}, steps={run['steps']}"
assert len(run["steps"]) == 3, f"expected 3 steps, got {len(run['steps'])}"
assert all(s["rc"] == 0 for s in run["steps"]), \
    f"not all steps succeeded: {[(s['id'],s['rc']) for s in run['steps']]}"
PY
}

# ---------------------------------------------------------------------------
# Test 3: parallel step failure sets overall rc to non-zero
# ---------------------------------------------------------------------------
test_parallel_failure_propagates() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  python3 - <<'PY' "$tmpdir/.local26/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
plan["scopes"][0]["steps"] = [
    {"id": "scope:web:0001", "type": "rsync", "host": "h1",
     "cmd": "exit 0", "parallel": True},
    {"id": "scope:web:0002", "type": "rsync", "host": "h1",
     "cmd": "exit 7", "parallel": True},  # this one fails
    {"id": "scope:web:0003", "type": "rsync", "host": "h1",
     "cmd": "exit 0", "parallel": True},
]
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub\n' >> "${LOCAL26_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL26_STUB_LOG="$tmpdir/calls.log"
  local deploy_rc=0
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" deploy \
      --plan "$tmpdir/.local26/plans/test.plan.json" \
      --scope web --max-parallel 3 --no-fail-fast \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail but rc=0"; return 1; }

  run_dir="$(ls -1 "$tmpdir/.local26/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local26/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] != 0, f"expected run-level failure, got rc=0"
failed = [s for s in run["steps"] if s["rc"] != 0]
assert len(failed) == 1, f"expected 1 failed step, got {len(failed)}: {failed}"
assert failed[0]["id"] == "scope:web:0002", f"wrong step failed: {failed[0]['id']}"
PY
}

# ---------------------------------------------------------------------------
# run all
# ---------------------------------------------------------------------------
test_parallel_flag_concurrent
test_parallel_barrier_override
test_parallel_failure_propagates

echo "test_parallel.sh: ok"
