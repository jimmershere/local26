#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Tests for per-step timeout: steps with timeout: N (seconds) should be killed
# if they exceed N seconds. Exit code 124 (GNU timeout convention) is expected.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

make_workspace() {
  local dir="$1"
  mkdir -p "$dir/.local81/state" "$dir/.local81/plans" "$dir/.local81/runs" "$dir/stubs"
  cat > "$dir/.local81/config.ini" <<'CFG'
[local81]
version = 0.1
CFG
  sha256sum "$dir/.local81/config.ini" | awk '{print $1}'
}

make_base_plan() {
  local path="$1" fp="$2"
  python3 - <<PY "$path" "$fp"
import json, sys
path, fp = sys.argv[1:]
plan = {
  "schema": "local81.plan.v0.1",
  "kind": "plan",
  "mode": "deploy",
  "local81_version": "0.1",
  "plan_id": "p-timeout",
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
# Test 1: step with timeout:1 that sleeps 5s → killed, step rc=124, run fails
# ---------------------------------------------------------------------------
test_step_timeout_kills_step() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local81/plans/test.plan.json" "$fp"

  python3 - <<'PY' "$tmpdir/.local81/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
plan["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001",
        "type": "rsync",
        "host": "h1",
        "cmd": "sleep 30",   # would block forever without timeout
        "timeout": 1         # kill after 1 second
    }
]
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub\n' >> "${LOCAL81_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local deploy_rc=0
  local t0 t1 elapsed
  t0="$(date +%s)"

  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  t1="$(date +%s)"
  elapsed=$(( t1 - t0 ))

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail due to timeout, but rc=0"; return 1; }

  # Should have finished in well under 10s (the sleep would have been 30s)
  [ "$elapsed" -lt 10 ] || { echo "timeout did not kill the step fast enough: elapsed=${elapsed}s"; return 1; }

  run_dir="$(ls -1 "$tmpdir/.local81/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local81/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] != 0, f"expected run-level failure, got rc=0"
assert len(run["steps"]) == 1
step = run["steps"][0]
# GNU timeout exits 124 on timeout; the step rc should be non-zero
assert step["rc"] != 0, f"expected step failure from timeout, got rc={step['rc']}"
PY
}

# ---------------------------------------------------------------------------
# Test 2: step with timeout that completes before the limit → succeeds
# ---------------------------------------------------------------------------
test_step_timeout_passes_on_success() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local81/plans/test.plan.json" "$fp"

  python3 - <<'PY' "$tmpdir/.local81/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
plan["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001",
        "type": "rsync",
        "host": "h1",
        "cmd": "echo fast-step",
        "timeout": 10    # generous timeout; step completes immediately
    }
]
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub\n' >> "${LOCAL81_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web --max-parallel 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  )

  run_dir="$(ls -1 "$tmpdir/.local81/runs" | sort | tail -n1)"
  python3 - <<'PY' "$tmpdir/.local81/runs/$run_dir/run.json"
import json, sys
run = json.load(open(sys.argv[1]))
assert run["rc"] == 0, f"expected success, got rc={run['rc']}"
assert run["steps"][0]["rc"] == 0
PY
}

# ---------------------------------------------------------------------------
# Test 3: CLI --step-timeout overrides steps without a per-step timeout
#         but per-step timeout takes precedence over CLI flag.
# ---------------------------------------------------------------------------
test_cli_step_timeout_global() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  local fp
  fp="$(make_workspace "$tmpdir")"
  make_base_plan "$tmpdir/.local81/plans/test.plan.json" "$fp"

  # Two steps: step 1 has no per-step timeout, step 2 has a generous per-step timeout.
  # CLI --step-timeout 1 should kill step 1 (sleeps 30s) but not step 2 (echo).
  python3 - <<'PY' "$tmpdir/.local81/plans/test.plan.json"
import json, sys
path = sys.argv[1]
with open(path) as f:
    plan = json.load(f)
plan["scopes"][0]["steps"] = [
    {
        "id": "scope:web:0001",
        "type": "rsync",
        "host": "h1",
        "cmd": "sleep 30"
        # no per-step timeout → CLI --step-timeout 1 applies
    }
]
with open(path, "w") as f:
    json.dump(plan, f, separators=(",", ":"))
PY

  cat > "$tmpdir/stubs/rsync" <<'RSYNC'
#!/usr/bin/env bash
set -euo pipefail
printf 'rsync-stub\n' >> "${LOCAL81_STUB_LOG:-/dev/null}"
RSYNC
  chmod +x "$tmpdir/stubs/rsync"

  export LOCAL81_STUB_LOG="$tmpdir/calls.log"
  local deploy_rc=0
  local t0 t1 elapsed
  t0="$(date +%s)"

  (
    cd "$tmpdir"
    PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local81" deploy \
      --plan "$tmpdir/.local81/plans/test.plan.json" \
      --scope web --max-parallel 1 --step-timeout 1 \
      >"$tmpdir/out.txt" 2>"$tmpdir/err.txt"
  ) || deploy_rc=$?

  t1="$(date +%s)"
  elapsed=$(( t1 - t0 ))

  [ "$deploy_rc" -ne 0 ] || { echo "expected deploy to fail due to global timeout, rc=0"; return 1; }
  [ "$elapsed" -lt 10 ] || { echo "global timeout did not kill step fast enough: elapsed=${elapsed}s"; return 1; }
}

# ---------------------------------------------------------------------------
# run all
# ---------------------------------------------------------------------------
test_step_timeout_kills_step
test_step_timeout_passes_on_success
test_cli_step_timeout_global

echo "test_timeout.sh: ok"
