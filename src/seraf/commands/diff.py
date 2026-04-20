from __future__ import annotations

import json
from pathlib import Path


def _load_plan(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _scope_map(plan: dict) -> dict[str, dict]:
    return {s["scope"]: s for s in plan.get("scopes", []) if "scope" in s}


def _step_set(scope: dict) -> dict[str, dict]:
    return {s["id"]: s for s in scope.get("steps", []) if "id" in s}


def diff_plans(plan_a_path: str, plan_b_path: str) -> str:
    """Produce a human-readable diff between two plan files."""
    try:
        plan_a = _load_plan(plan_a_path)
    except Exception as exc:
        return f"Failed to load plan A ({plan_a_path}): {exc}"
    try:
        plan_b = _load_plan(plan_b_path)
    except Exception as exc:
        return f"Failed to load plan B ({plan_b_path}): {exc}"

    lines = [
        "Seraf plan diff",
        "===============",
        f"Plan A: {plan_a.get('plan_id', plan_a_path)}",
        f"Plan B: {plan_b.get('plan_id', plan_b_path)}",
        "",
    ]

    # Top-level metadata diff
    meta_keys = ["seraf_version", "mode", "schema", "created_at", "config_fingerprint"]
    meta_changes: list[str] = []
    for key in meta_keys:
        val_a = plan_a.get(key)
        val_b = plan_b.get(key)
        if val_a != val_b:
            meta_changes.append(f"  {key}: {val_a!r} -> {val_b!r}")
    if meta_changes:
        lines.append("Metadata changes:")
        lines.extend(meta_changes)
        lines.append("")

    scopes_a = _scope_map(plan_a)
    scopes_b = _scope_map(plan_b)
    all_scopes = sorted(set(scopes_a) | set(scopes_b))

    for scope_name in all_scopes:
        if scope_name not in scopes_a:
            lines.append(f"Scope '{scope_name}': ADDED")
            step_count = len(scopes_b[scope_name].get("steps", []))
            lines.append(f"  Steps: {step_count}")
            lines.append("")
            continue
        if scope_name not in scopes_b:
            lines.append(f"Scope '{scope_name}': REMOVED")
            lines.append("")
            continue

        sa = scopes_a[scope_name]
        sb = scopes_b[scope_name]
        scope_changes: list[str] = []

        # Compare inputs
        inputs_a = sa.get("inputs", {})
        inputs_b = sb.get("inputs", {})
        for key in sorted(set(inputs_a) | set(inputs_b)):
            va = inputs_a.get(key)
            vb = inputs_b.get(key)
            if va != vb:
                scope_changes.append(f"  input {key}: {va!r} -> {vb!r}")

        # Compare discovery
        disc_a = sa.get("discovery", {})
        disc_b = sb.get("discovery", {})
        for key in sorted(set(disc_a) | set(disc_b)):
            va = disc_a.get(key)
            vb = disc_b.get(key)
            if va != vb:
                scope_changes.append(f"  discovery {key}: {va!r} -> {vb!r}")

        # Compare steps
        steps_a = _step_set(sa)
        steps_b = _step_set(sb)
        added = sorted(set(steps_b) - set(steps_a))
        removed = sorted(set(steps_a) - set(steps_b))
        common = sorted(set(steps_a) & set(steps_b))

        for sid in added:
            scope_changes.append(f"  step ADDED: {sid} [{steps_b[sid].get('type', 'step')}]")
        for sid in removed:
            scope_changes.append(f"  step REMOVED: {sid} [{steps_a[sid].get('type', 'step')}]")
        for sid in common:
            step_diffs: list[str] = []
            for key in ("cmd", "host", "type"):
                va = steps_a[sid].get(key)
                vb = steps_b[sid].get(key)
                if va != vb:
                    step_diffs.append(f"{key}: {va!r} -> {vb!r}")
            if step_diffs:
                scope_changes.append(f"  step CHANGED: {sid} ({', '.join(step_diffs)})")

        if scope_changes:
            lines.append(f"Scope '{scope_name}':")
            lines.extend(scope_changes)
            lines.append("")
        else:
            lines.append(f"Scope '{scope_name}': no changes")
            lines.append("")

    if len(lines) <= 5 and not any("ADDED" in l or "REMOVED" in l or "CHANGED" in l or "->" in l for l in lines):
        lines.append("Plans are identical.")

    return "\n".join(lines)


def run_diff(plan_a: str, plan_b: str) -> int:
    print(diff_plans(plan_a, plan_b))
    return 0
