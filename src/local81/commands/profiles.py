from __future__ import annotations

from pathlib import Path

from local81.profiles import list_profiles, profiles_dir, scaffold_profile


def run_profiles() -> int:
    names = list_profiles()
    print("Local-81 profiles")
    print("==============")
    if not names:
        print("No profiles found.")
        return 0
    for name in names:
        print(name)
    return 0


def run_profile_create(name: str) -> int:
    target = profiles_dir() / f"{name}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"Profile already exists: {target}")
        return 1
    target.write_text(scaffold_profile(name), encoding="utf-8")
    print(f"Created profile: {target}")
    return 0
