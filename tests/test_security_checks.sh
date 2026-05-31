#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$repo_root/tools/security-check.py"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/tools" "$tmpdir/src"
cp "$repo_root/tools/security-check.py" "$tmpdir/tools/security-check.py"
git -C "$tmpdir" init -q

cat > "$tmpdir/src/clean.py" <<'PY'
import subprocess

subprocess.run(["printf", "ok"], check=False)
PY
python3 "$tmpdir/tools/security-check.py" >"$tmpdir/clean.out"

cat > "$tmpdir/src/bad_shell.py" <<'PY'
import subprocess

subprocess.run("printf unsafe", shell=True, check=False)
PY
set +e
python3 "$tmpdir/tools/security-check.py" >"$tmpdir/bad-shell.out" 2>&1
bad_shell_rc=$?
set -e
[ "$bad_shell_rc" -ne 0 ]
grep -q 'subprocess shell=True is forbidden' "$tmpdir/bad-shell.out"
rm -f "$tmpdir/src/bad_shell.py"

cat > "$tmpdir/src/bad_bash_lc.py" <<'PY'
import subprocess

subprocess.run(["bash", "-lc", "printf unsafe"], check=False)
PY
set +e
python3 "$tmpdir/tools/security-check.py" >"$tmpdir/bad-bash-lc.out" 2>&1
bad_bash_lc_rc=$?
set -e
[ "$bad_bash_lc_rc" -ne 0 ]
grep -q 'new bash -lc execution site must be reviewed and approved' "$tmpdir/bad-bash-lc.out"

echo "test_security_checks.sh: ok"
