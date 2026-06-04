#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEB_DIR="${ROOT_DIR}/packaging/deb"
BUILD_DIR="${DEB_DIR}/.debbuild"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing required tool: %s\n' "$1" >&2
    exit 1
  }
}

need dpkg-deb

if [ "${1:-}" ]; then
  PACKAGE="$1"
else
  PACKAGE="$(find "${BUILD_DIR}/artifacts" -type f -name 'local81_*.deb' | sort | tail -n 1)"
fi

if [ ! -f "${PACKAGE}" ]; then
  printf 'package not found: %s\n' "${PACKAGE}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

dpkg-deb --info "${PACKAGE}" >/dev/null
dpkg-deb --contents "${PACKAGE}" >/dev/null
dpkg-deb -x "${PACKAGE}" "${TMP_DIR}/root"
dpkg-deb -e "${PACKAGE}" "${TMP_DIR}/control"

test -x "${TMP_DIR}/root/usr/bin/local81"
test -x "${TMP_DIR}/root/opt/local81/venv/bin/python"
test -f "${TMP_DIR}/root/etc/local81/local81.ini.example"

LOCAL81_HOME="${TMP_DIR}/root/opt/local81" "${TMP_DIR}/root/usr/bin/local81" --help >/dev/null
LOCAL81_HOME="${TMP_DIR}/root/opt/local81" "${TMP_DIR}/root/usr/bin/local81" help >/dev/null

printf 'Debian package smoke test passed: %s\n' "${PACKAGE}"
