#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RPM_DIR="${ROOT_DIR}/packaging/rpm"
TOPDIR="${RPM_DIR}/.rpmbuild"
SPEC="${RPM_DIR}/local81.spec"
VERSION="$(ROOT_DIR="${ROOT_DIR}" python3 - <<'PY'
from pathlib import Path
import os
import re
text = (Path(os.environ['ROOT_DIR']) / 'pyproject.toml').read_text(encoding='utf-8')
m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
print(m.group(1))
PY
)"
TARBALL="local81-${VERSION}.tar.gz"
SRCROOT="${TOPDIR}/SOURCES/local81-${VERSION}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required tool: $1" >&2
    exit 1
  }
}

need python3
need python3.12
need tar
need rsync
need rpmbuild

rm -rf "${TOPDIR}"
mkdir -p "${TOPDIR}"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
rm -rf "${SRCROOT}"
mkdir -p "${SRCROOT}"

rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  --exclude '.mypy_cache' \
  --exclude '.ruff_cache' \
  --exclude '*.pyc' \
  --exclude '*.egg-info' \
  --exclude 'build' \
  --exclude 'dist' \
  --exclude 'packaging/deb/.debbuild' \
  --exclude 'packaging/rpm/.rpmbuild' \
  "${ROOT_DIR}/" "${SRCROOT}/"

(
  cd "${TOPDIR}/SOURCES"
  tar czf "${TARBALL}" "local81-${VERSION}"
)

cp "${SPEC}" "${TOPDIR}/SPECS/"

echo "==> Building RPM in ${TOPDIR}"
rpmbuild \
  --define "_topdir ${TOPDIR}" \
  -ba "${TOPDIR}/SPECS/local81.spec"

echo
echo "Artifacts:"
find "${TOPDIR}" -type f \( -name '*.rpm' -o -name '*.src.rpm' \) | sort
