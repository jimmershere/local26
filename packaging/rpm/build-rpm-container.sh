#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME="${CONTAINER_RUNTIME:-docker}"
IMAGE="${LOCAL81_RPM_CONTAINER_IMAGE:-rockylinux:9}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

if ! command -v "${RUNTIME}" >/dev/null 2>&1; then
  printf 'missing required container runtime: %s\n' "${RUNTIME}" >&2
  printf 'Install Docker or set CONTAINER_RUNTIME to a compatible runtime such as podman.\n' >&2
  exit 1
fi

"${RUNTIME}" run --rm \
  -e "HOST_UID=${HOST_UID}" \
  -e "HOST_GID=${HOST_GID}" \
  -v "${ROOT_DIR}:/workspace/local81" \
  -w /workspace/local81 \
  "${IMAGE}" \
  /bin/bash -lc '
    set -euo pipefail
    dnf -y install \
      rpm-build \
      python3.12 \
      python3.12-devel \
      python3.12-pip \
      python3.12-setuptools \
      python3.12-wheel \
      rsync \
      tar \
      gzip \
      findutils \
      openssh-clients \
      make
    ./packaging/rpm/test-rpm.sh
    if [ -d packaging/rpm/.rpmbuild ]; then
      chown -R "${HOST_UID}:${HOST_GID}" packaging/rpm/.rpmbuild
    fi
  '
