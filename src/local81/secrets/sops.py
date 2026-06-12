"""SOPS-decrypt backend.

We shell out to the ``sops`` binary rather than re-implement its crypto: the
operator already trusts it for at-rest encryption, and the decrypted plaintext
only ever lives in memory here. The decrypted document is parsed as JSON and a
dotted ``key`` path is walked through it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from .errors import SecretBackendError, SecretNotFoundError


def sops_available() -> bool:
    return shutil.which("sops") is not None


def decrypt_value(file_path: str, dotted_key: str) -> str:
    if not sops_available():
        raise SecretBackendError("sops:// reference needs the 'sops' binary on PATH")
    try:
        completed = subprocess.run(
            ["sops", "-d", "--output-type", "json", "--", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:  # race: vanished between which() and run()
        raise SecretBackendError("sops binary disappeared from PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise SecretBackendError(f"sops decrypt of {file_path} timed out") from exc
    if completed.returncode != 0:
        raise SecretBackendError(
            f"sops failed to decrypt {file_path} (rc={completed.returncode}): {completed.stderr.strip()}"
        )
    try:
        document: Any = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SecretBackendError(f"sops output for {file_path} was not JSON") from exc
    return _walk(document, dotted_key, file_path)


def _walk(document: Any, dotted_key: str, file_path: str) -> str:
    node = document
    for part in dotted_key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise SecretNotFoundError(f"sops file {file_path} has no key path {dotted_key!r}")
    if isinstance(node, (dict, list)):
        raise SecretNotFoundError(
            f"sops key path {dotted_key!r} in {file_path} points at a container, not a scalar"
        )
    return str(node)
