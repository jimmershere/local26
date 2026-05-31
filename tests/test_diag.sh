#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

mkdir -p "$tmpdir/stubs"
cat > "$tmpdir/stubs/ssh" <<'SSH'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\n' "$*" >> "${LOCAL26_STUB_LOG}"
printf 'stdout:%s\n' "$1"
printf 'stderr:%s\n' "$1" >&2
SSH
chmod +x "$tmpdir/stubs/ssh"

export LOCAL26_STUB_LOG="$tmpdir/ssh.log"

out_dir="$tmpdir/diag-out"
PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" diag \
  --project m2-project \
  --hosts cmsap1,cmspr1 \
  --diag-type strace \
  --pid 4242 \
  --out-dir "$out_dir" >/dev/null

[ -f "$out_dir/diag-run.tsv" ]
[ -f "$out_dir/10.242.225.11.stdout.log" ]
[ -f "$out_dir/10.242.209.11.stderr.log" ]

python3 - <<'PY' "$out_dir/diag-run.tsv"
import csv,sys
path=sys.argv[1]
with open(path, newline='', encoding='utf-8') as f:
    rows=list(csv.DictReader(f, delimiter='\t'))
assert len(rows)==2, rows
hosts={r['host'] for r in rows}
assert hosts=={'10.242.225.11','10.242.209.11'}, hosts
for row in rows:
    assert row['rc']=='0', row
    assert 'strace -f -tt -s 256 -p 4242' in row['cmd'], row
PY

out_dir_dry="$tmpdir/diag-dry"
PATH="$tmpdir/stubs:$PATH" "$repo_root/bin/local26" diag \
  --hosts 127.0.0.1 \
  --remote-cmd 'uname -a' \
  --out-dir "$out_dir_dry" \
  --dry-run >/dev/null

if [ -f "$tmpdir/ssh.log" ]; then
  calls="$(wc -l < "$tmpdir/ssh.log")"
  [ "$calls" -eq 2 ]
fi

grep -q 'dry-run ssh 127.0.0.1 uname -a' "$out_dir_dry/127.0.0.1.stdout.log"

echo "test_diag.sh: ok"
