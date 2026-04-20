from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TextIO


@dataclass(slots=True)
class GuidedAnswers:
    project: str = ""
    scope_name: str = "main"
    source_dir: str = ""
    target_dir: str = ""
    remote_mkdir: bool = True
    servers: str = ""
    fail_fast: bool = True
    backup: bool = True
    backup_suffix: str = ".bkp"
    max_parallel: int = 4
    log_hosts: str = ""
    jboss_log_path: str = ""
    apache_log_path: str = ""
    engin_log_path: str = ""
    smartxfr_log_path: str = ""


def _section(title: str, *, out: TextIO = sys.stdout) -> None:
    out.write(f"\n== {title} ==\n")


def _prompt(message: str, default: str = "", *, inp: IO[str] = sys.stdin, out: TextIO = sys.stdout) -> str:
    if default:
        out.write(f"{message} [{default}]: ")
    else:
        out.write(f"{message}: ")
    out.flush()
    value = inp.readline()
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _prompt_bool(message: str, default: bool = True, *, inp: IO[str] = sys.stdin, out: TextIO = sys.stdout) -> bool:
    hint = "Y/n" if default else "y/N"
    out.write(f"{message} [{hint}]: ")
    out.flush()
    value = inp.readline()
    if value is None:
        return default
    value = value.strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def _prompt_int(message: str, default: int, *, inp: IO[str] = sys.stdin, out: TextIO = sys.stdout) -> int:
    out.write(f"{message} [{default}]: ")
    out.flush()
    value = inp.readline()
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        out.write(f"That does not look like a number, so I'll keep the default of {default}.\n")
        return default
    return parsed if parsed > 0 else default


def _normalize_servers(raw: str) -> str:
    tokens = raw.replace(",", " ").split()
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return ",".join(deduped)


def run_guided_interview(*, inp: IO[str] = sys.stdin, out: TextIO = sys.stdout) -> GuidedAnswers | None:
    answers = GuidedAnswers()
    cwd_name = Path.cwd().name

    out.write("\nWelcome to Seraf guided setup.\n")
    out.write("I'll help you build a working config for this project. We'll keep it simple: project name, scope, source, target, servers, and a few safety defaults. You can review everything before anything is written.\n")

    _section("Project identity", out=out)
    answers.project = _prompt("What should this project be called?", cwd_name, inp=inp, out=out)
    answers.scope_name = _prompt("What should the default scope be called?", "main", inp=inp, out=out)

    _section("Deployment source", out=out)
    answers.source_dir = _prompt("What local directory should Seraf deploy from?", inp=inp, out=out)
    if not answers.source_dir:
        out.write("I still need a source directory to build a usable config.\n")
        answers.source_dir = _prompt("Please enter the local source directory", inp=inp, out=out)
        if not answers.source_dir:
            out.write("Stopping here so we do not write a broken config.\n")
            return None
    source_path = Path(answers.source_dir)
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    if source_path.exists():
        out.write(f"Using source directory: {source_path}\n")
    else:
        keep_going = _prompt_bool(
            f"I can't find {answers.source_dir} yet. Continue anyway and keep it as a placeholder?",
            True,
            inp=inp,
            out=out,
        )
        if not keep_going:
            answers.source_dir = _prompt("Okay, what local directory should Seraf deploy from instead?", inp=inp, out=out)
            if not answers.source_dir:
                out.write("Stopping here so we do not write a broken config.\n")
                return None

    _section("Deployment target", out=out)
    answers.target_dir = _prompt("What remote target directory should files land in?", inp=inp, out=out)
    if not answers.target_dir:
        out.write("I still need a target directory to finish the config.\n")
        answers.target_dir = _prompt("Please enter the remote target directory", inp=inp, out=out)
        if not answers.target_dir:
            out.write("Stopping here so we do not write a broken config.\n")
            return None
    answers.remote_mkdir = _prompt_bool("Should Seraf create missing remote directories automatically?", True, inp=inp, out=out)

    _section("Servers", out=out)
    raw_servers = _prompt("Which servers should this scope deploy to?", inp=inp, out=out)
    if not raw_servers:
        out.write("I need at least one server before we can move on.\n")
        raw_servers = _prompt("Please enter one or more servers", inp=inp, out=out)
        if not raw_servers:
            out.write("Stopping here so we do not write a broken config.\n")
            return None
    answers.servers = _normalize_servers(raw_servers)
    out.write(f"Normalized server list: {answers.servers}\n")

    _section("Safety defaults", out=out)
    answers.fail_fast = _prompt_bool("Stop on the first failure?", True, inp=inp, out=out)
    answers.backup = _prompt_bool("Create backups before overwriting files?", True, inp=inp, out=out)
    if answers.backup:
        answers.backup_suffix = _prompt("Backup suffix", ".bkp", inp=inp, out=out)
    answers.max_parallel = _prompt_int("Maximum parallel workers (1 is a cautious first deploy)", 4, inp=inp, out=out)

    _section("Logs and diagnostics", out=out)
    want_logs = _prompt_bool("Do you want to set default log hosts now?", False, inp=inp, out=out)
    if want_logs:
        answers.log_hosts = _normalize_servers(_prompt("Log hosts", inp=inp, out=out))
        want_paths = _prompt_bool("Do you know the common log paths now?", False, inp=inp, out=out)
        if want_paths:
            answers.jboss_log_path = _prompt("JBoss log path", inp=inp, out=out)
            answers.apache_log_path = _prompt("Apache log path", inp=inp, out=out)
            answers.engin_log_path = _prompt("Engin log path", inp=inp, out=out)
            answers.smartxfr_log_path = _prompt("SmartXFR log path", inp=inp, out=out)
    else:
        out.write("No problem, we can leave logs for later.\n")

    return answers


def generate_config(answers: GuidedAnswers) -> str:
    lines = [
        "[seraf]",
        "version = 0.1",
        f"project = {answers.project}",
        f"default_scope = {answers.scope_name}",
        "state_dir = .seraf/state",
        "plans_dir = .seraf/plans",
        "runs_dir = .seraf/runs",
        "logs_dir = .seraf/logs",
        "lock_file = .seraf/seraf.lock",
        "require_plan_for_deploy = true",
        f"fail_fast = {'true' if answers.fail_fast else 'false'}",
        f"max_parallel = {answers.max_parallel}",
        "shell = /usr/bin/bash",
        "",
        "[tools]",
        "ssh = /usr/bin/ssh",
        "rsync = /usr/bin/rsync",
        "find = /usr/bin/find",
        "",
        "[defaults]",
        "rsync_opts = -az",
        f"backup = {'true' if answers.backup else 'false'}",
        f"backup_suffix = {answers.backup_suffix}",
        f"remote_mkdir = {'true' if answers.remote_mkdir else 'false'}",
        "dry_run_default = false",
        f"log_hosts = {answers.log_hosts}",
        "log_dest_dir = .seraf/pulled-logs",
        f"jboss_log_path = {answers.jboss_log_path}",
        f"apache_log_path = {answers.apache_log_path}",
        f"engin_log_path = {answers.engin_log_path}",
        f"smartxfr_log_path = {answers.smartxfr_log_path}",
        "",
        "[routing]",
        "env_from_filename_prefix = s:sys,q:qa,p:production",
        "env_from_server_name_char_at = 4",
        "env_from_server_name_char_map = s:sys,q:qa,p:production",
        "",
        f'[scope "{answers.scope_name}"]',
        "enabled = true",
        f"source_dir = {answers.source_dir}",
        f"target_dir = {answers.target_dir}",
        f"servers = {answers.servers}",
        "discovery = mtime_since_last_success",
        "rsync_opts = -az",
        f"backup = {'true' if answers.backup else 'false'}",
        f"backup_suffix = {answers.backup_suffix}",
        "",
    ]
    return "\n".join(lines) + "\n"


def preview_config(config_text: str, *, out: TextIO = sys.stdout) -> None:
    _section("Config preview", out=out)
    for line in config_text.splitlines():
        out.write(f"  {line}\n")
    out.write("\n")


def _write_project_files(answers: GuidedAnswers, config_text: str, *, out: TextIO = sys.stdout) -> int:
    seraf_dir = Path(".seraf")
    config_path = seraf_dir / "config.ini"
    seraf_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("state", "plans", "runs", "logs"):
        (seraf_dir / sub).mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text, encoding="utf-8")

    state = {
        "schema": "seraf.state.v0.1",
        "scope": answers.scope_name,
        "last_success": None,
        "last_plan_id": None,
        "last_run_id": None,
        "files_last_deployed_count": 0,
    }
    state_file = seraf_dir / "state" / f"{answers.scope_name}.json"
    state_file.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")

    out.write(f"Wrote {config_path}.\n")
    out.write(f"Seraf is ready for project '{answers.project}' with default scope '{answers.scope_name}'.\n")
    out.write("Next good steps: run 'seraf doctor', then 'seraf plan --summary'.\n")
    return 0


def run_guided(*, force: bool = False, inp: IO[str] = sys.stdin, out: TextIO = sys.stdout) -> int:
    config_path = Path(".seraf") / "config.ini"
    if config_path.exists() and not force:
        out.write(f"seraf: {config_path} already exists; rerun with --force\n")
        return 1

    while True:
        answers = run_guided_interview(inp=inp, out=out)
        if answers is None:
            out.write("Setup cancelled.\n")
            return 1

        config_text = generate_config(answers)
        preview_config(config_text, out=out)
        choice = _prompt("Write this config now? (write / edit / cancel)", "write", inp=inp, out=out).strip().lower()
        if choice == "cancel":
            out.write("Cancelled. No files written.\n")
            return 1
        if choice == "edit":
            out.write("Okay, let's run through it once more.\n")
            continue
        return _write_project_files(answers, config_text, out=out)
