#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# history renders through the shell wrapper
(
  cd "$tmpdir"
  mkdir -p .local81/runs/20260428T100000Z-ok .local81/runs/20260429T100000Z-fail
  cat > .local81/runs/20260428T100000Z-ok/run.json <<'JSON'
{"run_id":"20260428T100000Z-ok","plan_id":"plan-ok","started_at":"2026-04-28T10:00:00Z","finished_at":"2026-04-28T10:00:30Z","rc":0,"dry_run":false,"steps":[{"id":"s1","type":"rsync","host":"web1","cmd":"echo ok","rc":0,"started_at":"2026-04-28T10:00:00Z","finished_at":"2026-04-28T10:00:30Z","stdout":"ok","stderr":""}]}
JSON
  cat > .local81/runs/20260429T100000Z-fail/run.json <<'JSON'
{"run_id":"20260429T100000Z-fail","plan_id":"plan-fail","started_at":"2026-04-29T10:00:00Z","finished_at":"2026-04-29T10:01:00Z","rc":2,"dry_run":true,"steps":[{"id":"s2","type":"remote_cmd","host":"web2","cmd":"false","rc":2,"started_at":"2026-04-29T10:00:00Z","finished_at":"2026-04-29T10:01:00Z","stdout":"","stderr":"boom"}]}
JSON
  out="$($repo_root/bin/local81 history --limit 1 2>&1)"
  printf '%s\n' "$out" | grep -q "Local-81 history" || { printf 'FAIL: missing history header\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "20260429T100000Z-fail" || { printf 'FAIL: missing newest run\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "(dry run)" || { printf 'FAIL: missing dry-run marker\n'; exit 1; }
  if printf '%s\n' "$out" | grep -q "20260428T100000Z-ok"; then
    printf 'FAIL: --limit 1 should hide older runs\n'
    exit 1
  fi
)

# logs resolves exact and prefix run ids through the shell wrapper
(
  cd "$tmpdir"
  out="$($repo_root/bin/local81 logs 20260429 2>&1)"
  printf '%s\n' "$out" | grep -q "Local-81 run log" || { printf 'FAIL: missing logs header\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "20260429T100000Z-fail" || { printf 'FAIL: missing resolved run id\n'; exit 1; }
  printf '%s\n' "$out" | grep -q "stderr: boom" || { printf 'FAIL: missing stderr details\n'; exit 1; }
)

echo "test_history_logs.sh: ok"
