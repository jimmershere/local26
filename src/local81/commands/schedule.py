from __future__ import annotations

import shlex
import shutil
from argparse import Namespace

from local81.scheduling import (
    ScheduleDef,
    ScheduleError,
    ScheduleStore,
    install_hint,
)


def run_schedule(args: Namespace) -> int:
    store = ScheduleStore()
    command = args.schedule_command
    if command == "add":
        return _run_add(store, args)
    if command == "list":
        return _run_list(store)
    if command == "remove":
        return _run_remove(store, args)
    if command == "doctor":
        return _run_doctor(store)
    print(f"unknown schedule command: {command}")
    return 2


def _run_add(store: ScheduleStore, args: Namespace) -> int:
    try:
        command = shlex.split(args.command_str)
    except ValueError as exc:
        print(f"could not parse --command: {exc}")
        return 1
    if not command:
        print("--command must not be empty")
        return 1
    defn = ScheduleDef(
        name=args.name,
        command=command,
        on_calendar=args.on_calendar,
        notify_url=args.notify_url,
        description=args.description,
        working_dir=args.working_dir,
    )
    try:
        written = store.save(defn)
    except ScheduleError as exc:
        print(f"cannot add schedule: {exc}")
        return 1
    print(f"Added schedule '{defn.name}' (OnCalendar={defn.on_calendar}).")
    print("Rendered files:")
    for path in written:
        print(f"  {path}")
    print()
    print(install_hint(store, defn.name))
    return 0


def _run_list(store: ScheduleStore) -> int:
    defs = store.list()
    if not defs:
        print("No schedules defined. Add one with 'local81 schedule add NAME --command ... --on-calendar ...'.")
        return 0
    print(f"Schedules ({len(defs)}):")
    for defn in defs:
        notify = f" notify={defn.notify_url}" if defn.notify_url else ""
        print(f"  {defn.name}: OnCalendar={defn.on_calendar} cmd={' '.join(defn.command)}{notify}")
    return 0


def _run_remove(store: ScheduleStore, args: Namespace) -> int:
    try:
        removed = store.remove(args.name)
    except ScheduleError as exc:
        print(f"cannot remove schedule: {exc}")
        return 1
    print(f"Removed schedule '{args.name}'. Deleted {len(removed)} file(s).")
    print("If you installed the units, also run:")
    print(f"  sudo systemctl disable --now local81-{args.name}.timer")
    print(f"  sudo rm -f /etc/systemd/system/local81-{args.name}.service /etc/systemd/system/local81-{args.name}.timer")
    return 0


def _run_doctor(store: ScheduleStore) -> int:
    print("Local-81 schedule doctor")
    print("============")
    systemctl = shutil.which("systemctl")
    flock = shutil.which("flock")
    print(f"[{'PASS' if systemctl else 'WARN'}] binary:systemctl: {systemctl or 'missing (units cannot be installed here)'}")
    print(f"[{'PASS' if flock else 'WARN'}] binary:flock: {flock or 'missing (overlap protection unavailable here)'}")

    defs = store.list()
    print(f"[PASS] schedules:count: {len(defs)} defined")
    failures = 0
    for defn in defs:
        try:
            from local81.scheduling import validate

            validate(defn)
            print(f"[PASS] schedule:{defn.name}: valid (OnCalendar={defn.on_calendar})")
        except ScheduleError as exc:
            failures += 1
            print(f"[FAIL] schedule:{defn.name}: {exc}")
    if failures:
        print(f"\nFound {failures} invalid schedule(s).")
        return 1
    return 0
