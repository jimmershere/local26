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
servers = localhost
backup = true
backup_suffix = .bkp

[test2]
source_dir = ${src_dir}
target_dir = /srv/test2
servers = localhost
backup = false
CFG

(
  cd "$tmpdir"
  "$repo_root/bin/seraf" init --force --project demo >/dev/null
)

python - <<'PY' "$tmpdir/.seraf/state/test1.json" "$tmpdir/.seraf/state/test2.json"
import json,sys
for p in sys.argv[1:]:
    with open(p) as f:
        data=json.load(f)
    data["last_success"]=None
    with open(p,"w") as f:
        json.dump(data,f,separators=(",",":"))
PY

plan_json="$(cd "$tmpdir" && "$repo_root/bin/seraf" plan --format json --stdout)"

python - <<'PY' "$plan_json"
import json,sys
plan=json.loads(sys.argv[1])
assert plan["schema"]=="seraf.plan.v0.1"
assert plan["kind"]=="plan"
assert plan["mode"]=="deploy"
assert plan["config_fingerprint"].startswith("sha256:")
assert len(plan["scopes"])==2

scopes={s["scope"]: s for s in plan["scopes"]}

scope=scopes["test1"]
steps=scope["steps"]
assert steps, "expected steps for test1"
rsync=[s for s in steps if s["type"]=="rsync"]
assert len(rsync)==2, len(rsync)
for step in rsync:
    assert " --backup " in step["cmd"], step["cmd"]
    assert "--suffix=.bkp" in step["cmd"], step["cmd"]
    rb=step["rollback"]
    assert rb is not None
    assert ".bkp" in rb["cmd"], rb["cmd"]
    assert step["remote_path"] in rb["cmd"], rb["cmd"]

scope2=scopes["test2"]
steps2=scope2["steps"]
assert steps2, "expected steps for test2"
rsync2=[s for s in steps2 if s["type"]=="rsync"]
assert len(rsync2)==2, len(rsync2)
for step in rsync2:
    assert "--backup" not in step["cmd"], step["cmd"]
    assert "--suffix=" not in step["cmd"], step["cmd"]
    assert step["rollback"] is None
PY

echo "test_plan.sh: ok"
