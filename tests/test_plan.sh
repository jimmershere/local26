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

git_src="${tmpdir}/git-src"
mkdir -p "$git_src/app"
(
  cd "$git_src"
  /usr/bin/git init >/dev/null
  /usr/bin/git config user.email test@example.com
  /usr/bin/git config user.name test
  printf 'from-git' > app/from_git.txt
  /usr/bin/git add app/from_git.txt
  /usr/bin/git commit -m init >/dev/null
)
git_sha="$(cd "$git_src" && /usr/bin/git rev-parse HEAD)"

cat >> "${tmpdir}/.seraf/config.ini" <<CFG

[scope "git1"]
enabled = true
workspace = git
repo_url = ${git_src}
ref = HEAD
workspace_dir = .seraf/workspaces/git1
source_subdir = app
target_dir = /srv/git
servers = localhost
discovery = mtime_since_last_success
rsync_opts = -az
backup = false
backup_suffix = .bkp
remote_mkdir = true
CFG

python3 - <<'PY' "$tmpdir/.seraf/state/test1.json" "$tmpdir/.seraf/state/test2.json" "$tmpdir/.seraf/state/git1.json"
import json,sys
for p in sys.argv[1:3]:
    with open(p) as f:
        data=json.load(f)
    data["last_success"]=None
    with open(p,"w") as f:
        json.dump(data,f,separators=(",",":"))
with open(sys.argv[3],"w") as f:
    json.dump({"schema":"seraf.state.v0.1","scope":"git1","last_success":None,"last_plan_id":None,"last_run_id":None,"files_last_deployed_count":0},f,separators=(",",":"))
PY

plan_json="$(cd "$tmpdir" && "$repo_root/bin/seraf" plan --format json --stdout)"

python3 - <<'PY' "$plan_json" "$git_sha"
import json,sys
plan=json.loads(sys.argv[1])
expected_git_sha=sys.argv[2]
assert plan["schema"]=="seraf.plan.v0.1"
assert plan["kind"]=="plan"
assert plan["mode"]=="deploy"
assert plan["config_fingerprint"].startswith("sha256:")
assert len(plan["scopes"])==3

scopes={s["scope"]: s for s in plan["scopes"]}

scope=scopes["test1"]
steps=scope["steps"]
assert steps, "expected steps for test1"
assert "workspace_provider" not in scope["inputs"], scope["inputs"]
assert all(s["type"] != "remote_cmd" for s in steps), steps
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
assert all(s["type"] != "remote_cmd" for s in steps2), steps2
rsync2=[s for s in steps2 if s["type"]=="rsync"]
assert len(rsync2)==3, len(rsync2)
for step in rsync2:
    assert "--backup" not in step["cmd"], step["cmd"]
    assert "--suffix=" not in step["cmd"], step["cmd"]
    assert step["rollback"] is None

git_scope=scopes["git1"]
inputs=git_scope["inputs"]
assert inputs["workspace_provider"]=="git", inputs
assert inputs["commit_sha"]==expected_git_sha, inputs
assert inputs["workspace_dir"].endswith(f"/checkouts/{expected_git_sha}/app"), inputs["workspace_dir"]
rsync_git=[s for s in git_scope["steps"] if s["type"]=="rsync"]
assert len(rsync_git)==1, rsync_git
assert f"/checkouts/{expected_git_sha}/app/from_git.txt" in rsync_git[0]["local_path"], rsync_git[0]
PY

echo "test_plan.sh: ok"
