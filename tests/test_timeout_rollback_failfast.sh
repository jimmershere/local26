#!/usr/bin/env bash
# Tests for: step timeout, rollback on failure, fail_fast enforcement
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ─── helpers ──────────────────────────────────────────────────────────────────

make_workspace() {
  local dir="$1"
  mkdir -p "$dir/.local81/state" "$dir/.local81/plans" "$dir/.local81/runs" "$dir/stubs"
  cat > "$dir/.local81/config.ini" <<'CFG'
[local81]
version = 0.1
CFG

  local fp
  fp="$(sha256sum "$dir/.local81/config.ini" | awk '{print $1}')"

  # Write plan with 3 rsync steps; rollback cmds are bash -lc echo strings
  python3 - <<'PY' "$dir/.local81/plans/test.plan.json" "$fp"
import json, sys
path, fp = sys.argv[1:]
plan = {
  "schema":        "local81.plan.v0.1",
  "kind":          "plan",
  "mode":          "deploy",
  "local81_version": "0.1",
  "plan_id":       "p1",
  "created_at":    "2024-01-01T00:00:00Z",
  "config_fingerprint": f"sha256:{fp}",
  "scopes": [{
    "scope": "web",
    "steps": [
      {
        "id":   "scope:web:0001",
        "type": "rsync",
        "host": "h1",
        "cmd":  "rsync -az -- \"/tmp/a\" \"h1:/srv/a\"",
        "rollback": {"type": "restore", "cmd": "echo rollback-a"},
      },
      {
        "id":   "scope:web:0002",
        "type": "rsync",
        "host": "h1",
        "cmd":  "rsync -az -- \"/tmp/b\" \"h1:/srv/b\"",
        "rollback": {"type": "restore", "cmd": "echo rollback-b"},
      },
      {
        "id":   "scope:web:0003",
        "type": "rsync",
        "host": "h1",
        "cmd":  "rsync -az -- \"/tmp/c\" \"h1:/srv/c\"",
        "rollback": {"type": "restore", "cmd": "echo rollback-c"},
      },
    ],
    "summary": {"counts": {"mkdir_steps":0,"rsync_steps":3,"rollbackable_steps":3,"warnings":[]}}
  }],
  "analysis": {"ai": {"enabled": False}}
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  # stub: records calls; supports LOCAL81_FAIL_STEP env (1-based index)
  cat > "$dir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
n=0
nfile="${LOCAL81_STUB_LOG}.count"
[ -f "$nfile" ] && n="$(cat "$nfile")"
n=$((n + 1))
printf '%s' "$n" > "$nfile"
printf 'rsync-call-%d %s\n' "$n" "$*" >> "${LOCAL81_STUB_LOG}"
fail_step="${LOCAL81_FAIL_STEP:-0}"
[ "$fail_step" -eq 0 ] || [ "$n" -ne "$fail_step" ] || exit 5
RSYNC
  chmod +x "$dir/stubs/rsync"

  cat > "$dir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
printf 'ssh %s\n' "$*" >> "${LOCAL81_STUB_LOG}"
SSH
  chmod +x "$dir/stubs/ssh"
}

# ─── test: --step-timeout kills a slow step ───────────────────────────────────

test_step_timeout() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  # Replace step 0001 with a slow sleep command via a slow-rsync stub
  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync %s\n' "$*" >> "${LOCAL81_STUB_LOG}"
if [[ "$*" == *"/tmp/a"* ]]; then
  sleep 30
fi
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local rc=0
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web \
      --max-parallel 1 \
      --step-timeout 2 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || rc=$?

  [ "$rc" -ne 0 ] || { echo "FAIL test_step_timeout: expected non-zero rc, got 0"; return 1; }

  # run.json must exist; timed-out step rc should be 124 (GNU timeout)
  local run_dir
  run_dir="$(ls -1 "$tmpdir/.local81/runs" | LC_ALL=C sort | tail -n1)"
  local run_json="$tmpdir/.local81/runs/$run_dir/run.json"
  [ -f "$run_json" ] || { echo "FAIL test_step_timeout: run.json missing"; return 1; }

  python3 - <<'PY' "$run_json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] != 0, f"run rc should be non-zero, got {run['rc']}"
# Step 1 should have rc=124 (timeout) or at least non-zero
step1 = run["steps"][0]
assert step1["rc"] != 0, f"step1 rc should be non-zero (timed out), got {step1['rc']}"
PY

  printf 'test_step_timeout: ok\n'
}

# ─── test: --rollback-on-failure runs rollback cmds in reverse ────────────────

test_rollback_on_failure() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  # Capture rollback outputs to a file
  local rb_log="$tmpdir/rollback-output.log"

  # Override plan so rollback cmds write to $rb_log
  local fp
  fp="$(sha256sum "$tmpdir/.local81/config.ini" | awk '{print $1}')"
  python3 - <<'PY' "$tmpdir/.local81/plans/test.plan.json" "$fp" "$rb_log"
import json, sys
path, fp, rb_log = sys.argv[1:]
plan = {
  "schema":        "local81.plan.v0.1",
  "kind":          "plan",
  "mode":          "deploy",
  "local81_version": "0.1",
  "plan_id":       "p1",
  "created_at":    "2024-01-01T00:00:00Z",
  "config_fingerprint": f"sha256:{fp}",
  "scopes": [{
    "scope": "web",
    "steps": [
      {
        "id":   "scope:web:0001",
        "type": "rsync",
        "host": "h1",
        "cmd":  "rsync -az -- \"/tmp/a\" \"h1:/srv/a\"",
        "rollback": {"type": "restore", "cmd": f"echo rb-a >> {rb_log}"},
      },
      {
        "id":   "scope:web:0002",
        "type": "rsync",
        "host": "h1",
        "cmd":  "rsync -az -- \"/tmp/b\" \"h1:/srv/b\"",
        "rollback": {"type": "restore", "cmd": f"echo rb-b >> {rb_log}"},
      },
    ],
    "summary": {"counts": {"mkdir_steps":0,"rsync_steps":2,"rollbackable_steps":2,"warnings":[]}}
  }],
  "analysis": {"ai": {"enabled": False}}
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  # Stub: step 2 fails
  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
n=0
nfile="${LOCAL81_STUB_LOG}.count"
[ -f "$nfile" ] && n="$(cat "$nfile")"
n=$((n + 1))
printf '%s' "$n" > "$nfile"
printf 'rsync-call-%d\n' "$n" >> "${LOCAL81_STUB_LOG}"
[ "$n" -ne 2 ] || exit 7
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local rc=0
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web \
      --max-parallel 1 \
      --rollback-on-failure \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || rc=$?

  [ "$rc" -ne 0 ] || { echo "FAIL test_rollback_on_failure: expected non-zero deploy rc"; return 1; }

  # rollback.log should be written
  local run_dir
  run_dir="$(ls -1 "$tmpdir/.local81/runs" | LC_ALL=C sort | tail -n1)"
  local rollback_log="$tmpdir/.local81/runs/$run_dir/rollback.log"
  [ -f "$rollback_log" ] || { echo "FAIL test_rollback_on_failure: rollback.log not written"; return 1; }

  # Only prior successful steps should be rolled back; here step 1 succeeded then step 2 failed.
  python3 - <<'PY' "$rb_log"
import sys, os
path = sys.argv[1]
if not os.path.exists(path):
    raise AssertionError(f"rollback output log not found: {path}")
lines = [l.strip() for l in open(path) if l.strip()]
assert lines == ["rb-a"], f"expected only rb-a rollback output, got: {lines}"
PY

  printf 'test_rollback_on_failure: ok\n'
}

# ─── test: fail_fast stops subsequent steps after first failure ───────────────

test_fail_fast() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  # 3-step plan; step 1 fails; steps 2+3 should be skipped
  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
n=0
nfile="${LOCAL81_STUB_LOG}.count"
[ -f "$nfile" ] && n="$(cat "$nfile")"
n=$((n + 1))
printf '%s' "$n" > "$nfile"
printf 'rsync-call-%d\n' "$n" >> "${LOCAL81_STUB_LOG}"
[ "$n" -ne 1 ] || exit 3
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local rc=0
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web \
      --max-parallel 1 \
      --fail-fast \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || rc=$?

  [ "$rc" -ne 0 ] || { echo "FAIL test_fail_fast: expected non-zero rc"; return 1; }

  # Only 1 rsync call should have been made (step 1 failed, 2+3 skipped)
  local call_count
  call_count="$(wc -l < "$LOCAL81_STUB_LOG" | tr -d ' ')"
  [ "$call_count" -eq 1 ] || { echo "FAIL test_fail_fast: expected 1 rsync call, got $call_count"; return 1; }

  # run.json should record 3 steps: rc=3, rc=-1, rc=-1
  local run_dir
  run_dir="$(ls -1 "$tmpdir/.local81/runs" | LC_ALL=C sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local81/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] != 0, f"run rc should be non-zero"
assert len(run["steps"]) == 3, f"expected 3 steps, got {len(run['steps'])}"
assert run["steps"][0]["rc"] == 3, f"step1 rc should be 3 (failed), got {run['steps'][0]['rc']}"
assert run["steps"][1]["rc"] == -1, f"step2 rc should be -1 (skipped), got {run['steps'][1]['rc']}"
assert run["steps"][2]["rc"] == -1, f"step3 rc should be -1 (skipped), got {run['steps'][2]['rc']}"
PY

  printf 'test_fail_fast: ok\n'
}

# ─── test: no-fail-fast lets all steps run despite failure ────────────────────

test_no_fail_fast() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
n=0
nfile="${LOCAL81_STUB_LOG}.count"
[ -f "$nfile" ] && n="$(cat "$nfile")"
n=$((n + 1))
printf '%s' "$n" > "$nfile"
printf 'rsync-call-%d\n' "$n" >> "${LOCAL81_STUB_LOG}"
[ "$n" -ne 1 ] || exit 3
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local rc=0
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web \
      --max-parallel 1 \
      --no-fail-fast \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || rc=$?

  [ "$rc" -ne 0 ] || { echo "FAIL test_no_fail_fast: expected non-zero rc (step 1 failed)"; return 1; }

  # All 3 rsync calls should have been made
  local call_count
  call_count="$(wc -l < "$LOCAL81_STUB_LOG" | tr -d ' ')"
  [ "$call_count" -eq 3 ] || { echo "FAIL test_no_fail_fast: expected 3 rsync calls, got $call_count"; return 1; }

  local run_dir
  run_dir="$(ls -1 "$tmpdir/.local81/runs" | LC_ALL=C sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local81/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert len(run["steps"]) == 3, f"expected 3 steps, got {len(run['steps'])}"
# step1 failed; step2+3 ran (rc=0)
assert run["steps"][0]["rc"] == 3, f"step1 rc wrong: {run['steps'][0]['rc']}"
assert run["steps"][1]["rc"] == 0, f"step2 should have run, got rc {run['steps'][1]['rc']}"
assert run["steps"][2]["rc"] == 0, f"step3 should have run, got rc {run['steps'][2]['rc']}"
PY

  printf 'test_no_fail_fast: ok\n'
}

# ─── test: rollback without failure = no rollback.log ────────────────────────

test_rollback_no_failure_no_log() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  make_workspace "$tmpdir"

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
printf 'rsync %s\n' "$*" >> "${LOCAL81_STUB_LOG}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web \
      --max-parallel 1 \
      --rollback-on-failure \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )

  local run_dir
  run_dir="$(ls -1 "$tmpdir/.local81/runs" | LC_ALL=C sort | tail -n1)"
  # rollback.log must NOT exist when all steps succeed
  [ ! -f "$tmpdir/.local81/runs/$run_dir/rollback.log" ] || {
    echo "FAIL test_rollback_no_failure_no_log: rollback.log should not exist on success"
    return 1
  }

  printf 'test_rollback_no_failure_no_log: ok\n'
}

# ─── run all ──────────────────────────────────────────────────────────────────

test_step_timeout
test_rollback_on_failure
test_fail_fast
test_no_fail_fast
test_rollback_no_failure_no_log

echo "test_timeout_rollback_failfast.sh: ok"
