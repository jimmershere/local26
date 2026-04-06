from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CheckResult:
    level: str
    name: str
    detail: str

    def render(self) -> str:
        return f"[{self.level}] {self.name}: {self.detail}"


def _binary_check(name: str, *, required: bool = True) -> CheckResult:
    resolved = shutil.which(name)
    if resolved:
        return CheckResult("PASS", f"binary:{name}", resolved)
    level = "FAIL" if required else "WARN"
    return CheckResult(level, f"binary:{name}", "missing from PATH")


def _dir_check(path_str: str) -> CheckResult:
    path = Path(path_str).expanduser()
    if not path.exists():
        return CheckResult("WARN", f"dir:{path_str}", "does not exist")
    if not path.is_dir():
        return CheckResult("FAIL", f"dir:{path_str}", "exists but is not a directory")
    try:
        probe = path / ".seraf-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult("PASS", f"dir:{path_str}", "exists and writable")
    except Exception:
        return CheckResult("WARN", f"dir:{path_str}", "exists but is not writable")


def _plan_checks(plan_path: Path) -> list[CheckResult]:
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        results = [CheckResult("PASS", "plan:json", str(plan_path))]
    except Exception as exc:
        return [CheckResult("FAIL", "plan:json", str(exc))]

    required_keys = ["kind", "mode", "schema", "plan_id", "scopes"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        results.append(CheckResult("FAIL", "plan:schema", f"missing keys: {', '.join(missing)}"))
    else:
        results.append(CheckResult("PASS", "plan:schema", "required keys present"))

    results.append(CheckResult("PASS" if data.get("kind") == "plan" else "FAIL", "plan:kind", f"got {data.get('kind')!r}"))
    results.append(CheckResult("PASS" if data.get("mode") == "deploy" else "FAIL", "plan:mode", f"got {data.get('mode')!r}"))
    results.append(CheckResult("PASS" if data.get("schema") == "seraf.plan.v0.1" else "FAIL", "plan:schema_ver", f"got {data.get('schema')!r}"))

    scopes = data.get("scopes", [])
    if isinstance(scopes, list) and scopes:
        results.append(CheckResult("PASS", "plan:scopes", f"count={len(scopes)}"))
    else:
        results.append(CheckResult("WARN", "plan:scopes", "no scopes found"))

    total_steps = 0
    if isinstance(scopes, list):
        for scope in scopes:
            if isinstance(scope, dict):
                steps = scope.get("steps", [])
                if isinstance(steps, list):
                    total_steps += len(steps)
    results.append(CheckResult("PASS" if total_steps > 0 else "WARN", "plan:steps", f"count={total_steps}"))
    return results


def run_doctor(plan: str | None = None) -> int:
    checks: list[CheckResult] = [
        _binary_check("bash"),
        _binary_check("python3"),
        _binary_check("ssh"),
        _binary_check("rsync"),
        _binary_check("find"),
        _binary_check("sha256sum"),
        _binary_check("git", required=False),
        _dir_check("~/.seraf"),
        _dir_check(".seraf"),
        _dir_check(".seraf/plans"),
        _dir_check(".seraf/runs"),
        _dir_check(".seraf/state"),
    ]
    if plan:
        checks.extend(_plan_checks(Path(plan)))
    for check in checks:
        print(check.render())
    return 1 if any(check.level == "FAIL" for check in checks) else 0
