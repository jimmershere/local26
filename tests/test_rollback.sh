#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Tests for rollback-on-failure and on_failure hooks.
#
# Rollback (--rollback-on-failure): when a step fails, previously successful
# steps that have a rollback.cmd are undone in LIFO order.
#
# on_failure: per-step hook runs immediately after the step fails.
# Global on_failure (plan-level) runs once if any step fails.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

make_workspace() {
  local dir="$1"
  mkdir -p "$dir/.local26/state" "$dir/.local26/plans" "$dir/.local26/runs" "$dir/stubs"
  cat > "$dir/.local26/config.ini" <<'CFG'
[local26]
version = 0.1
CFG
  sha256sum "$dir/.local26/config.ini" | awk '{print $1}'
}

make_base_plan() {
  local path="$1" fp="$2"
  python3 - <<PY "$path" "$fp"
import json, sys
path, fp = sys.argv[1:]
plan = {
  "schema": "local26.plan.v0.1",
  "kind": "plan",
  "mode": "deploy",
  "local26_version": "0.1",
  "plan_id": "p-rollback",
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
# Test 1: --rollback-on-failure runs rollback cmds for successful steps
#         in reverse order when a later step fails.
# ---------------------------------------------------------------------------
test_rollback_runs_on_failure() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  local rb_log="$tmpdir/rollback_calls.txt"

  python3 - <<PY "$tmpdir/.local26/plans/test.plan.json" "$rb_log"
import json, sys
path, rb_log = sys.argv[1:]
plan_data = json.load(open(path))
plan_data["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001", "type": "rsync", "host": "h1",
        "cmd": "echo step-1",
        "rollback": {"type": "custom", "cmd": f"printf 'rollback-1\\n' >> {rb_log}"}
    },
    {
        "id": "scope:web:0002", "type": "rsync", "host": "h1",
        "cmd": "echo step-2",
        "rollback": {"type": "custom", "cmd": f"printf 'rollback-2\\n' >> {rb_log}"}
    },
    {
        "id": "scope:web:0003", "type": "rsync", "host": "h1",
        "cmd": "exit 5",    # this step fails
        "rollback": None    # no rollback for the failing step itself
    },
]
with open(path, "w") as f:
    json.dump(plan_data, f, separators=(",", ":"))
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
      --scope web --max-parallel 1 --rollback-on-failure \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail, got rc=0"; return 1; }

  # Rollback log must exist and contain rollback-2 before rollback-1 (LIFO).
  # Normalize whitespace because shells/printf may leave trailing spaces/newlines.
  [ -f "$rb_log" ] || { echo "rollback log not created"; return 1; }
  local normalized
  normalized="$(tr '\n\t' '  ' < "$rb_log" | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
  [ "$normalized" = "rollback-2 rollback-1" ] || {
    echo "expected LIFO rollback order 'rollback-2 rollback-1', got: '$normalized'"
    return 1
  }

  # run.json should record the failure
  run_dir="$(ls -1 "$tmpdir/.local26/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local26/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] != 0
failed = [s for s in run["steps"] if s["rc"] != 0]
assert len(failed) == 1 and failed[0]["id"] == "scope:web:0003"
PY
}

# ---------------------------------------------------------------------------
# Test 2: without --rollback-on-failure, rollback cmds are NOT executed.
# ---------------------------------------------------------------------------
test_no_rollback_without_flag() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  local rb_log="$tmpdir/rollback_calls.txt"

  python3 - <<PY "$tmpdir/.local26/plans/test.plan.json" "$rb_log"
import json, sys
path, rb_log = sys.argv[1:]
plan_data = json.load(open(path))
plan_data["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001", "type": "rsync", "host": "h1",
        "cmd": "echo step-1",
        "rollback": {"type": "custom", "cmd": f"printf 'rollback-1\\n' >> {rb_log}"}
    },
    {
        "id": "scope:web:0002", "type": "rsync", "host": "h1",
        "cmd": "exit 3"   # fails
    },
]
with open(path, "w") as f:
    json.dump(plan_data, f, separators=(",", ":"))
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
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail, got rc=0"; return 1; }
  [ ! -f "$rb_log" ] || { echo "rollback log should NOT exist without --rollback-on-failure"; return 1; }
}

# ---------------------------------------------------------------------------
# Test 3: per-step on_failure hook fires when that step fails.
# ---------------------------------------------------------------------------
test_per_step_on_failure_hook() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  local hook_log="$tmpdir/hook_calls.txt"

  python3 - <<PY "$tmpdir/.local26/plans/test.plan.json" "$hook_log"
import json, sys
path, hook_log = sys.argv[1:]
plan_data = json.load(open(path))
plan_data["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001", "type": "rsync", "host": "h1",
        "cmd": "exit 0"
        # no on_failure — hook must NOT fire on success
    },
    {
        "id": "scope:web:0002", "type": "rsync", "host": "h1",
        "cmd": "exit 6",
        "on_failure": {"cmd": f"printf 'hook-fired\\n' >> {hook_log}"}
    },
]
with open(path, "w") as f:
    json.dump(plan_data, f, separators=(",", ":"))
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
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail, got rc=0"; return 1; }
  [ -f "$hook_log" ] || { echo "on_failure hook was not fired"; return 1; }
  grep -qF "hook-fired" "$hook_log" || { echo "hook log content unexpected: $(cat "$hook_log")"; return 1; }
}

# ---------------------------------------------------------------------------
# Test 4: global on_failure hook (plan-level) fires once when any step fails.
# ---------------------------------------------------------------------------
test_global_on_failure_hook() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  local global_log="$tmpdir/global_hook.txt"

  python3 - <<PY "$tmpdir/.local26/plans/test.plan.json" "$global_log"
import json, sys
path, global_log = sys.argv[1:]
plan_data = json.load(open(path))
# Add global on_failure hook at plan level
plan_data["on_failure"] = {"cmd": f"printf 'global-hook-fired\\n' >> {global_log}"}
plan_data["scopes"][0]["steps"] = [
    {"id": "scope:web:0001", "type": "rsync", "host": "h1", "cmd": "echo ok"},
    {"id": "scope:web:0002", "type": "rsync", "host": "h1", "cmd": "exit 4"},
]
with open(path, "w") as f:
    json.dump(plan_data, f, separators=(",", ":"))
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
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail, got rc=0"; return 1; }
  [ -f "$global_log" ] || { echo "global on_failure hook was not fired"; return 1; }
  grep -qF "global-hook-fired" "$global_log" || { echo "global hook log unexpected: $(cat "$global_log")"; return 1; }
}

# ---------------------------------------------------------------------------
# Test 5: on_failure does NOT fire when all steps succeed.
# ---------------------------------------------------------------------------
test_on_failure_not_fired_on_success() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local26/plans/test.plan.json" "$fp"

  local hook_log="$tmpdir/hook.txt"

  python3 - <<PY "$tmpdir/.local26/plans/test.plan.json" "$hook_log"
import json, sys
path, hook_log = sys.argv[1:]
plan_data = json.load(open(path))
plan_data["on_failure"] = {"cmd": f"printf 'should-not-fire\\n' >> {hook_log}"}
plan_data["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001", "type": "rsync", "host": "h1",
        "cmd": "echo ok",
        "on_failure": {"cmd": f"printf 'step-hook-should-not-fire\\n' >> {hook_log}"}
    },
]
with open(path, "w") as f:
    json.dump(plan_data, f, separators=(",", ":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub\n' >> "${LOCAL26_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL26_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" deploy \
      --plan "$tmpdir/.local26/plans/test.plan.json" \
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )

  [ ! -f "$hook_log" ] || { echo "on_failure hook should NOT fire on success; got: $(cat "$hook_log")"; return 1; }
}

# ---------------------------------------------------------------------------
# run all
# ---------------------------------------------------------------------------
test_rollback_runs_on_failure
test_no_rollback_without_flag
test_per_step_on_failure_hook
test_global_on_failure_hook
test_on_failure_not_fired_on_success

echo "test_rollback.sh: ok"
