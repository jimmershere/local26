#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "${tmpdir}/settings.cfg" <<'CFG'
[web]
source_dir = /tmp/seraf-web
 target_dir=/srv/web
servers = z1, a1 ,b1

[api]
source_dir=/tmp/seraf-api
target_dir=/srv/api
servers=api2,api1
CFG

mkdir -p /tmp/seraf-web /tmp/seraf-api
printf 'old' > /tmp/seraf-web/old.txt
printf 'new' > /tmp/seraf-web/new.txt
printf 'z' > /tmp/seraf-api/z.txt
printf 'a' > /tmp/seraf-api/a.txt

touch -d '2023-01-01 00:00:00 UTC' /tmp/seraf-web/old.txt
touch -d '2025-01-01 00:00:00 UTC' /tmp/seraf-web/new.txt
touch -d '2024-03-01 00:00:00 UTC' /tmp/seraf-api/z.txt
touch -d '2024-02-01 00:00:00 UTC' /tmp/seraf-api/a.txt

(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --force --project demo >/dev/null
)

python - <<'PY' "$tmpdir/.seraf/state/web.json"
import json,sys
p=sys.argv[1]
with open(p) as f:
    data=json.load(f)
data["last_success"]="2024-01-01T00:00:00Z"
with open(p,"w") as f:
    json.dump(data,f,separators=(",",":"))
PY

plan_id="$(cd "$tmpdir" && "$repo_root/bin/seraf" plan)"
plan_file="${tmpdir}/.seraf/plans/${plan_id}.plan.json"

test -f "$plan_file"

python - <<'PY' "$tmpdir" "$plan_file"
import hashlib,json,sys
root,plan_path=sys.argv[1],sys.argv[2]
with open(plan_path) as f:
    plan=json.load(f)
assert plan["schema"]=="seraf.plan.v0.1"
assert plan["analysis"]["ai"]["enabled"] is False
cfg=open(f"{root}/.seraf/config.ini","rb").read()
assert plan["config_fingerprint"]==hashlib.sha256(cfg).hexdigest()
scopes=[s["scope"] for s in plan["scopes"]]
assert scopes==sorted(scopes)
web=next(s for s in plan["scopes"] if s["scope"]=="web")
api=next(s for s in plan["scopes"] if s["scope"]=="api")
assert web["servers"]==["a1","b1","z1"]
assert api["servers"]==["api1","api2"]
assert web["files"]==["new.txt"]
assert api["files"]==["a.txt","z.txt"]
PY

rm -rf /tmp/seraf-web /tmp/seraf-api

echo "test_plan.sh: ok"
