"""Minimal OpenBao / HashiCorp Vault KV v2 read client (stdlib only).

We deliberately implement just the read path we need rather than pull in
``hvac``: it keeps the stdlib-first guarantee and the attack surface tiny. TLS
verification is on by default and can only be relaxed by an explicit, loud
config flag (``BAO_SKIP_VERIFY``) — never silently.

Auth token resolution order:
1. ``BAO_TOKEN`` / ``VAULT_TOKEN`` environment variables.
2. AppRole login via ``BAO_ROLE_ID`` + ``BAO_SECRET_ID`` (also stdlib urllib).
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from .errors import SecretBackendError, SecretForbiddenError, SecretNotFoundError

DEFAULT_ADDR = "http://127.0.0.1:8200"
_TIMEOUT_SECONDS = 10.0


def _addr() -> str:
    return (os.environ.get("BAO_ADDR") or os.environ.get("VAULT_ADDR") or DEFAULT_ADDR).rstrip("/")


def _ssl_context() -> ssl.SSLContext | None:
    if os.environ.get("BAO_SKIP_VERIFY", "").lower() in {"1", "true", "yes"}:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None  # urllib uses its verifying default context


@dataclass(slots=True)
class BaoClient:
    addr: str
    token: str

    @classmethod
    def from_env(cls) -> BaoClient:
        token = _resolve_token()
        return cls(addr=_addr(), token=token)

    def read_kv2(self, mount: str, path: str, key: str) -> str:
        url = f"{self.addr}/v1/{mount}/data/{path}"
        body = self._get(url)
        try:
            data = body["data"]["data"]
        except (KeyError, TypeError) as exc:
            raise SecretNotFoundError(f"bao secret {mount}/{path} has no data payload") from exc
        if key not in data:
            raise SecretNotFoundError(f"bao secret {mount}/{path} has no key {key!r}")
        return str(data[key])

    def _get(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"X-Vault-Token": self.token})
        return self._send(request)

    def _send(self, request: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS, context=_ssl_context()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (403,):
                raise SecretForbiddenError(f"bao denied access ({exc.code}) for {request.full_url}") from exc
            if exc.code in (404,):
                raise SecretNotFoundError(f"bao has no secret at {request.full_url}") from exc
            raise SecretBackendError(f"bao request failed ({exc.code}) for {request.full_url}") from exc
        except urllib.error.URLError as exc:
            raise SecretBackendError(f"bao unreachable at {request.full_url}: {exc.reason}") from exc


def _resolve_token() -> str:
    token = os.environ.get("BAO_TOKEN") or os.environ.get("VAULT_TOKEN")
    if token:
        return token
    role_id = os.environ.get("BAO_ROLE_ID")
    secret_id = os.environ.get("BAO_SECRET_ID")
    if role_id and secret_id:
        return _approle_login(role_id, secret_id)
    raise SecretBackendError(
        "no OpenBao token: set BAO_TOKEN/VAULT_TOKEN or BAO_ROLE_ID + BAO_SECRET_ID"
    )


def _approle_login(role_id: str, secret_id: str) -> str:
    url = f"{_addr()}/v1/auth/approle/login"
    payload = json.dumps({"role_id": role_id, "secret_id": secret_id}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS, context=_ssl_context()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 403):
            raise SecretForbiddenError(f"bao AppRole login denied ({exc.code})") from exc
        raise SecretBackendError(f"bao AppRole login failed ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise SecretBackendError(f"bao unreachable for AppRole login: {exc.reason}") from exc
    try:
        return str(body["auth"]["client_token"])
    except (KeyError, TypeError) as exc:
        raise SecretBackendError("bao AppRole login returned no client_token") from exc
