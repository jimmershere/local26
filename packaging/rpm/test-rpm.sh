#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RPM_DIR="${ROOT_DIR}/packaging/rpm"
SPEC="${RPM_DIR}/local81.spec"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing required tool: %s\n' "$1" >&2
    exit 1
  }
}

need python3

bash -n "${RPM_DIR}/build-rpm.sh"
bash -n "${ROOT_DIR}/packaging/common/local81-wrapper"
bash -n "${RPM_DIR}/scripts/local81-wrapper"

PROJECT_VERSION="$(ROOT_DIR="${ROOT_DIR}" python3 - <<'PY'
from pathlib import Path
import os
import re

text = (Path(os.environ["ROOT_DIR"]) / "pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
if not match:
    raise SystemExit("could not read version from pyproject.toml")
print(match.group(1))
PY
)"
SPEC_VERSION="$(awk '/^Version:/ {print $2; exit}' "${SPEC}")"
if [ "${PROJECT_VERSION}" != "${SPEC_VERSION}" ]; then
  printf 'RPM spec version %s does not match pyproject.toml version %s\n' "${SPEC_VERSION}" "${PROJECT_VERSION}" >&2
  exit 1
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
  printf 'RPM validation skipped: rpmbuild is not installed. Run ./packaging/rpm/build-rpm.sh on a RHEL/Rocky builder with rpmbuild and Python 3.12.\n'
  exit 0
fi

"${RPM_DIR}/build-rpm.sh"

RPM_ARTIFACT="$(find "${RPM_DIR}/.rpmbuild/RPMS" -type f -name 'local81-*.rpm' | sort | tail -n 1)"
if [ ! -f "${RPM_ARTIFACT}" ]; then
  printf 'RPM artifact not found under %s\n' "${RPM_DIR}/.rpmbuild/RPMS" >&2
  exit 1
fi

if command -v rpm >/dev/null 2>&1; then
  rpm -qip "${RPM_ARTIFACT}" >/dev/null
  rpm -qlp "${RPM_ARTIFACT}" >/dev/null
else
  printf 'RPM inspection skipped: rpm is not installed, but rpmbuild produced %s\n' "${RPM_ARTIFACT}"
fi

printf 'RPM package validation passed: %s\n' "${RPM_ARTIFACT}"
