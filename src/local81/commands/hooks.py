from __future__ import annotations

from local81.hooks import list_hooks


def run_hooks() -> int:
    statuses = list_hooks()
    print("Local-81 hooks")
    print("===========")
    for status in statuses:
        if not status.exists:
            state = "missing"
        elif status.executable:
            state = "installed"
        else:
            state = "present, not executable"
        print(f"{status.name}: {state} ({status.path})")
    return 0
