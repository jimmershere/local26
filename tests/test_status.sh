#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# ── Test 1: status with no runs ──────────────────────────────────────────────
(
  cd "$tmpdir"
  mkdir -p .local81/runs
  out="$("$repo_root/bin/local81" status 2>&1)"
  printf '%s\n' "$out" | grep -q "Local-81 status" || { printf 'FAIL: missing header\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "None right now" || { printf 'FAIL: expected no active runs message\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "No completed runs found yet" || { printf 'FAIL: expected no-runs message\n'; exit 1; }
)

# ── Test 2: status reads from last run.json ──────────────────────────────────
(
  cd "$tmpdir"
  local_run_dir=".local81/runs/20260101T000000Z-99999"
  mkdir -p "$local_run_dir"
  cat > "${local_run_dir}/run.json" <<'JSON'
{"run_id":"20260101T000000Z-99999","plan_id":"test-plan","started_at":"2026-01-01T00:00:00Z","finished_at":"2026-01-01T00:01:00Z","rc":0,"dry_run":false,"steps":[]}
JSON
  out="$("$repo_root/bin/local81" status 2>&1)"
  printf '%s\n' "$out" | grep -q "pass" || { printf 'FAIL: expected pass in status output\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "20260101T000000Z-99999" || { printf 'FAIL: run_id not found\n'; exit 1; }
)

# ── Test 3: failed run shows fail ────────────────────────────────────────────
(
  cd "$tmpdir"
  local_run_dir2=".local81/runs/20260102T000000Z-88888"
  mkdir -p "$local_run_dir2"
  cat > "${local_run_dir2}/run.json" <<'JSON'
{"run_id":"20260102T000000Z-88888","plan_id":"test-plan","started_at":"2026-01-02T00:00:00Z","finished_at":"2026-01-02T00:01:00Z","rc":1,"dry_run":false,"steps":[]}
JSON
  out="$("$repo_root/bin/local81" status 2>&1)"
  printf '%s\n' "$out" | grep -q "fail" || { printf 'FAIL: expected fail in status output\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "20260102T000000Z-88888" || { printf 'FAIL: last run_id not found\n'; exit 1; }
)

# ── Test 4: status reads from state file if present ─────────────────────────
(
  cd "$tmpdir"
  mkdir -p "${HOME}/.local81"
  state_file="${HOME}/.local81/state.json"
  cat > "$state_file" <<'JSON'
{"last_run_id":"state-run-001","last_result":"pass","last_run_at":"2026-03-01T12:00:00Z","last_rc":0}
JSON
  out="$("$repo_root/bin/local81" status 2>&1)"
  rm -f "$state_file"
  printf '%s\n' "$out" | grep -q "state-run-001" || { printf 'FAIL: state file run_id not found\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "pass" || { printf 'FAIL: expected pass from state file\n'; exit 1; }
)

echo "test_status.sh: ok"
