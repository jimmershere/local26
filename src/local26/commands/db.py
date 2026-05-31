from __future__ import annotations

from argparse import Namespace

from local26.db.runner import run_database_command


def run_db(args: Namespace) -> int:
    return run_database_command(args)
