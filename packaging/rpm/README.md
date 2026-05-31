# Local-81 RPM scaffold

This directory contains the first operator-grade RPM packaging scaffold for Local-81.

## Packaging model

Current install layout:

- `/usr/bin/local81`, operator entrypoint wrapper
- `/opt/local81/app`, application source, docs, and packaging payload
- `/opt/local81/venv`, isolated runtime virtualenv populated at build/install time
- `/etc/local81/local81.ini.example`, packaged config example
- `/var/lib/local81`, runtime state directory
- `/var/lib/local81` ownership intended for `local81:local81`

## Why this layout

Local-81 is not yet shaped like a native system Python package for stock RHEL8. It currently:

- targets Python `>=3.12`
- depends on `PyYAML`
- carries both Python and shell entrypoints
- is better presented as an application bundle under `/opt/local81`

That makes an `/opt/local81` payload with a stable `/usr/bin/local81` wrapper the safest first professional package shape.

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
3. Local-81's packaged runtime/config contract still needs a final decision, specifically whether packaged runs should default to `/var/lib/local81` or remain repo-local.

## Next hardening steps

- add a tested config lookup strategy for `/etc/local81` and `/var/lib/local81`
- decide whether to vendor wheels vs. build online in the RPM buildroot
- add CI that runs `rpmbuild -ba` in a clean Rocky/RHEL-compatible builder
