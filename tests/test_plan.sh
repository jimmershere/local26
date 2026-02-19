#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

src_dir="${tmpdir}/src"
mkdir -p "${src_dir}/sub/nested"
printf 'a' > "${src_dir}/sub/a.txt"
printf 'b' > "${src_dir}/sub/b.txt"
printf 'c' > "${src_dir}/sub/nested/hello world.txt"

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

python3 - <<'PY' "$tmpdir/.seraf/state/test1.json" "$tmpdir/.seraf/state/test2.json"
import json,sys
for p in sys.argv[1:]:
    with open(p) as f:
        data=json.load(f)
    data["last_success"]=None
    with open(p,"w") as f:
        json.dump(data,f,separators=(",",":"))
PY

plan_json="$(cd "$tmpdir" && "$repo_root/bin/seraf" plan --format json --stdout)"

python3 - <<'PY' "$plan_json"
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
assert len(rsync)==3, len(rsync)
mkdir_steps=[s for s in steps if s["type"]=="mkdir"]
assert mkdir_steps, "expected mkdir steps for test1"
for step in mkdir_steps:
    assert step["cmd"].startswith('ssh "localhost" "mkdir -p -- '), step["cmd"]
    assert '\\"' in step["cmd"], step["cmd"]

space_steps=[s for s in rsync if "hello world.txt" in s["local_path"]]
assert len(space_steps)==1, len(space_steps)
space_cmd=space_steps[0]["cmd"]
assert '"' + space_steps[0]["local_path"] + '"' in space_cmd, space_cmd
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
assert len(rsync2)==3, len(rsync2)
for step in rsync2:
    assert "--backup" not in step["cmd"], step["cmd"]
    assert "--suffix=" not in step["cmd"], step["cmd"]
    assert step["rollback"] is None
PY

echo "test_plan.sh: ok"
