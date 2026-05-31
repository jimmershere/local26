#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# Set up a minimal project with a source dir
src_dir="${tmpdir}/src"
mkdir -p "${src_dir}"
printf 'hello' > "${src_dir}/file.txt"

cat > "${tmpdir}/settings.cfg" <<CFG
[myapp]
source_dir = ${src_dir}
target_dir = /srv/app
servers = testhost
backup = false
CFG

(
  cd "$tmpdir"
  "$repo_root/bin/local26" init --force --project summarytest >/dev/null

  # Clear last_success so all files are selected
  python3 - <<'PY' "$tmpdir/.local26/state/myapp.json"
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
d["last_success"] = None
with open(sys.argv[1], "w") as f:
    json.dump(d, f, separators=(",",":"))
PY

  # ── Test 1: --summary outputs compact one-liners ──────────────────────────
  out="$("$repo_root/bin/local26" plan --summary 2>&1)"

  # Should have pipe-delimited lines
  line_count="$(printf '%s\n' "$out" | grep -c '|' || true)"
  [ "$line_count" -gt 0 ] || { printf 'FAIL: no summary lines found\n'; exit 1; }

  # Each line should match: id | type | timeout | status
  while IFS= read -r line; do
    [[ "$line" == *" | "* ]] || { printf 'FAIL: line missing pipe delimiter: %s\n' "$line"; exit 1; }
    col_count="$(printf '%s\n' "$line" | awk -F'|' '{print NF}')"
    [ "$col_count" -eq 4 ] || { printf 'FAIL: expected 4 columns, got %s in: %s\n' "$col_count" "$line"; exit 1; }
  done < <(printf '%s\n' "$out" | grep '|')

  # Each line should contain a step id like scope:myapp:NNNN
  printf '%s\n' "$out" | grep -q "scope:myapp:" || { printf 'FAIL: expected scope:myapp: in summary\n'; exit 1; }

  # Status column should be "pending" for a fresh plan
  printf '%s\n' "$out" | grep -q "pending" || { printf 'FAIL: expected pending status\n'; exit 1; }

  # ── Test 2: --summary does NOT print the plan_id line ─────────────────────
  printf '%s\n' "$out" | grep -qvE '^[0-9]{8}T[0-9]{6}Z-' || true  # just make sure there's other content
  # The output should only contain pipe lines (no bare plan_id)
  plan_id_lines="$(printf '%s\n' "$out" | grep -cE '^[0-9]{8}T[0-9]{6}Z-[a-f0-9]+$' || true)"
  [ "$plan_id_lines" -eq 0 ] || { printf 'FAIL: --summary should not print plan_id line\n'; exit 1; }

  # ── Test 3: plan file is still written (non-ci mode) ─────────────────────
  plan_count="$(find .local26/plans -name '*.plan.json' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$plan_count" -ge 1 ] || { printf 'FAIL: plan file not written with --summary\n'; exit 1; }

  # ── Test 4: --summary works combined with --scope ─────────────────────────
  out2="$("$repo_root/bin/local26" plan --summary --scope myapp 2>&1)"
  printf '%s\n' "$out2" | grep -q "scope:myapp:" || { printf 'FAIL: --summary --scope did not produce myapp steps\n'; exit 1; }
)

echo "test_plan_summary.sh: ok"
