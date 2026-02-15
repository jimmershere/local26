#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

src_dir="${tmpdir}/src"
mkdir -p "${src_dir}/sub"
printf 'a' > "${src_dir}/sub/a.txt"
printf 'b' > "${src_dir}/sub/b.txt"

cat > "${tmpdir}/settings.cfg" <<CFG
[test1]
source_dir = ${src_dir}
target_dir = /srv/test
servers = localhost,host2
CFG

(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --force --project demo >/dev/null
)

python - <<'PY' "$tmpdir/.seraf/state/test1.json"
import json,sys
p=sys.argv[1]
with open(p) as f:
    data=json.load(f)
data["last_success"]=None
with open(p,"w") as f:
    json.dump(data,f,separators=(",",":"))
PY

plan_json="$(cd "$tmpdir" && "$repo_root/bin/seraf" plan --scope test1 --format json --stdout)"

python - <<'PY' "$plan_json"
import json,sys
plan=json.loads(sys.argv[1])
assert plan["schema"]=="seraf.plan.v0.1"
assert plan["kind"]=="plan"
assert plan["mode"]=="deploy"
assert plan["config_fingerprint"].startswith("sha256:")
assert len(plan["scopes"])==1
scope=plan["scopes"][0]
assert scope["scope"]=="test1"
steps=scope["steps"]
assert steps, "expected steps"
mkdir=[s for s in steps if s["type"]=="mkdir"]
rsync=[s for s in steps if s["type"]=="rsync"]
assert len(mkdir)==2, len(mkdir)
assert len(rsync)==4, len(rsync)
counts=scope["summary"]["counts"]
assert counts["mkdir_steps"]==2
assert counts["rsync_steps"]==4
ids=[s["id"] for s in steps]
assert ids==sorted(ids), ids
assert ids[0]=="scope:test1:0001"
assert ids[-1]=="scope:test1:0006"
PY

echo "test_plan.sh: ok"
