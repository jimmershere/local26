from __future__ import annotations

from .adapters import DatabaseAdapter
from .models import DatabaseTarget
from .oracle import Oracle19cAdapter
from .postgres import Postgres17Adapter
from .sqlite import SQLiteAdapter

ADAPTERS: dict[str, type[DatabaseAdapter]] = {
    "oracle19c": Oracle19cAdapter,
    "postgres17": Postgres17Adapter,
    "sqlite": SQLiteAdapter,
}


def adapter_for(target: DatabaseTarget) -> DatabaseAdapter:
    try:
        adapter_type = ADAPTERS[target.engine]
    except KeyError as exc:
        raise ValueError(f"unsupported database engine: {target.engine}") from exc
    return adapter_type(target)
