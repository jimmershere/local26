#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# ── Test 1: basic doctor passes for required binaries ────────────────────────
(
  cd "$tmpdir"
  out="$("$repo_root/bin/seraf" doctor 2>&1)" || true
  # bash, python3, ssh, rsync, find, sha256sum should all be present in test env
  printf '%s\n' "$out" | grep -q "binary:bash" || { printf 'FAIL: binary:bash missing\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "binary:python3" || { printf 'FAIL: binary:python3 missing\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "binary:rsync" || { printf 'FAIL: binary:rsync missing\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "binary:find" || { printf 'FAIL: binary:find missing\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "binary:sha256sum" || { printf 'FAIL: binary:sha256sum missing\n'; exit 1; }
)

# ── Test 2: doctor reports missing dirs as warn ──────────────────────────────
(
  cd "$tmpdir"
  out="$("$repo_root/bin/seraf" doctor 2>&1)" || true
  # .seraf doesn't exist here → should warn
  printf '%s\n' "$out" | grep -q "dir:.seraf" || { printf 'FAIL: dir:.seraf check missing\n'; exit 1; }
  printf '%s\n' "$out" | grep -qE '\[WARN\].*dir:.seraf' || { printf 'FAIL: .seraf should be WARN (not exist)\n'; exit 1; }
)

# ── Test 3: doctor with writable .seraf dirs shows pass ─────────────────────
(
  cd "$tmpdir"
  mkdir -p .seraf/plans .seraf/runs .seraf/state
  out="$("$repo_root/bin/seraf" doctor 2>&1)" || true
  printf '%s\n' "$out" | grep -E 'dir:\.seraf:' | grep -q "\[PASS\]" || { printf 'FAIL: .seraf should PASS when writable\n'; exit 1; }
)

# ── Test 4: doctor --plan with valid plan ────────────────────────────────────
(
  cd "$tmpdir"
  plan_file="${tmpdir}/valid.plan.json"
  cat > "$plan_file" <<'JSON'
{
  "seraf_version": "0.1",
  "kind": "plan",
  "mode": "deploy",
  "schema": "seraf.plan.v0.1",
  "plan_id": "20260101T000000Z-abc12345",
  "created_at": "2026-01-01T00:00:00Z",
  "config_fingerprint": "sha256:deadbeef",
  "scopes": [
    {
      "scope": "test",
      "inputs": {},
      "steps": [{"id":"scope:test:0001","type":"rsync","host":"srv1","cmd":"rsync -az ./a b"}]
    }
  ]
}
JSON
  out="$("$repo_root/bin/seraf" doctor --plan "$plan_file" 2>&1)"
  printf '%s\n' "$out" | grep -q "plan:json" || { printf 'FAIL: plan:json check missing\n'; exit 1; }
  printf '%s\n' "$out" | grep "plan:json" | grep -q "\[PASS\]" || { printf 'FAIL: valid plan json should PASS\n'; exit 1; }
  printf '%s\n' "$out" | grep "plan:kind" | grep -q "\[PASS\]" || { printf 'FAIL: plan:kind should PASS\n'; exit 1; }
  printf '%s\n' "$out" | grep "plan:mode" | grep -q "\[PASS\]" || { printf 'FAIL: plan:mode should PASS\n'; exit 1; }
)

# ── Test 5: doctor --plan with invalid plan fails ────────────────────────────
(
  cd "$tmpdir"
  bad_plan="${tmpdir}/bad.plan.json"
  cat > "$bad_plan" <<'JSON'
{
  "kind": "notaplan",
  "mode": "wrong",
  "schema": "seraf.plan.v0.1",
  "plan_id": "bad",
  "scopes": []
}
JSON
  out="$("$repo_root/bin/seraf" doctor --plan "$bad_plan" 2>&1)" || true
  printf '%s\n' "$out" | grep "plan:kind" | grep -q "\[FAIL\]" || { printf 'FAIL: bad kind should FAIL\n'; exit 1; }
  printf '%s\n' "$out" | grep "plan:mode" | grep -q "\[FAIL\]" || { printf 'FAIL: bad mode should FAIL\n'; exit 1; }
)

# ── Test 6: doctor --plan with invalid JSON fails ────────────────────────────
(
  cd "$tmpdir"
  broken="${tmpdir}/broken.json"
  printf 'not json at all\n' > "$broken"
  out="$("$repo_root/bin/seraf" doctor --plan "$broken" 2>&1)" || true
  printf '%s\n' "$out" | grep "plan:json" | grep -q "\[FAIL\]" || { printf 'FAIL: broken json should FAIL\n'; exit 1; }
)

echo "test_doctor.sh: ok"
