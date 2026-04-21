#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RPM_DIR="${ROOT_DIR}/packaging/rpm"
TOPDIR="${RPM_DIR}/.rpmbuild"
SPEC="${RPM_DIR}/seraf.spec"
VERSION="$(ROOT_DIR="${ROOT_DIR}" python3 - <<'PY'
from pathlib import Path
import os
import re
text = (Path(os.environ['ROOT_DIR']) / 'pyproject.toml').read_text(encoding='utf-8')
m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
print(m.group(1))
PY
)"
TARBALL="seraf-${VERSION}.tar.gz"
SRCROOT="${TOPDIR}/SOURCES/seraf-${VERSION}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required tool: $1" >&2
    exit 1
  }
}

need python3
need tar
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
  --exclude 'packaging/rpm/.rpmbuild' \
  "${ROOT_DIR}/" "${SRCROOT}/"

(
  cd "${TOPDIR}/SOURCES"
  tar czf "${TARBALL}" "seraf-${VERSION}"
)

cp "${SPEC}" "${TOPDIR}/SPECS/"

echo "==> Building RPM in ${TOPDIR}"
rpmbuild \
  --define "_topdir ${TOPDIR}" \
  -ba "${TOPDIR}/SPECS/seraf.spec"

echo
echo "Artifacts:"
find "${TOPDIR}" -type f \( -name '*.rpm' -o -name '*.src.rpm' \) | sort
