# Seraf RPM scaffold

This directory contains the first operator-grade RPM packaging scaffold for Seraf.

## Packaging model

Current install layout:

- `/usr/bin/seraf`, operator entrypoint wrapper
- `/opt/seraf/app`, application source, docs, and packaging payload
- `/opt/seraf/venv`, isolated runtime virtualenv populated at build/install time
- `/etc/seraf/seraf.ini.example`, packaged config example
- `/var/lib/seraf`, runtime state directory
- `/var/lib/seraf` ownership intended for `seraf:seraf`

## Why this layout

Seraf is not yet shaped like a native system Python package for stock RHEL8. It currently:

- targets Python `>=3.12`
- depends on `PyYAML`
- carries both Python and shell entrypoints
- is better presented as an application bundle under `/opt/seraf`

That makes an `/opt/seraf` payload with a stable `/usr/bin/seraf` wrapper the safest first professional package shape.

## Build prerequisites

Expected on the RPM build host:

- `rpmbuild`
- `python3`
- `python3.12`
- `python3.12-devel`
- `python3.12-pip`
- `python3.12-setuptools`
- `python3.12-wheel`
- `tar`
- `rsync`

## Local build

From the repo root:

```bash
chmod +x packaging/rpm/build-rpm.sh
./packaging/rpm/build-rpm.sh
```

Artifacts, when the toolchain is present, land under:

```text
packaging/rpm/.rpmbuild/RPMS/
packaging/rpm/.rpmbuild/SRPMS/
```

## Current known blockers

1. `rpmbuild` is not available in the current execution environment.
2. The project requires Python 3.12+, which is not a standard base RHEL8 runtime.
3. Seraf's packaged runtime/config contract still needs a final decision, specifically whether packaged runs should default to `/var/lib/seraf` or remain repo-local.

## Next hardening steps

- add a tested config lookup strategy for `/etc/seraf` and `/var/lib/seraf`
- decide whether to vendor wheels vs. build online in the RPM buildroot
- add CI that runs `rpmbuild -ba` in a clean Rocky/RHEL-compatible builder
