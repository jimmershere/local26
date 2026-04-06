from __future__ import annotations

import json
from pathlib import Path


def load_scope_state(scope: str, root: str | Path = ".") -> dict:
    path = Path(root) / ".seraf" / "state" / f"{scope}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
