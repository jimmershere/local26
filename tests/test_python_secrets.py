from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from local81.secrets import (
    BaoClient,
    SecretForbiddenError,
    SecretNotFoundError,
    SecretRefSyntaxError,
    SecretResolver,
    is_secret_ref,
    parse_ref,
    validate_refs,
)


# --- ref parsing -----------------------------------------------------------


def test_parse_env_ref() -> None:
    ref = parse_ref("env://DB_PASSWORD")
    assert ref.scheme == "env"
    assert ref.location == "DB_PASSWORD"
    assert ref.key is None


def test_parse_bao_ref() -> None:
    ref = parse_ref("bao://secret/prod/db#password")
    assert ref.scheme == "bao"
    assert ref.location == "secret/prod/db"
    assert ref.key == "password"


def test_parse_sops_ref() -> None:
    ref = parse_ref("sops://secrets.enc.json#db.password")
    assert ref.scheme == "sops"
    assert ref.location == "secrets.enc.json"
    assert ref.key == "db.password"


def test_is_secret_ref_rejects_literals() -> None:
    assert not is_secret_ref("hunter2")
    assert is_secret_ref("env://X")
    assert is_secret_ref("bao://m/p#k")


def test_parse_rejects_bare_literal() -> None:
    with pytest.raises(SecretRefSyntaxError):
        parse_ref("hunter2")


def test_parse_rejects_unknown_scheme() -> None:
    with pytest.raises(SecretRefSyntaxError):
        parse_ref("aws://thing#k")


def test_parse_bao_requires_key_fragment() -> None:
    with pytest.raises(SecretRefSyntaxError):
        parse_ref("bao://secret/prod/db")


def test_parse_bao_requires_mount_and_path() -> None:
    with pytest.raises(SecretRefSyntaxError):
        parse_ref("bao://justmount#key")


def test_parse_env_rejects_fragment() -> None:
    with pytest.raises(SecretRefSyntaxError):
        parse_ref("env://NAME#oops")


def test_validate_refs_collects_syntax_errors() -> None:
    errors = validate_refs(["env://OK", "literal-not-a-ref", "bad://x#k"])
    assert len(errors) == 2


# --- env backend -----------------------------------------------------------


def test_resolve_env_ref() -> None:
    resolver = SecretResolver(env={"DB_PASSWORD": "s3cret"})
    assert resolver.resolve("env://DB_PASSWORD") == "s3cret"


def test_resolve_env_missing_fails_fast() -> None:
    resolver = SecretResolver(env={})
    with pytest.raises(SecretNotFoundError):
        resolver.resolve("env://NOPE")


def test_resolve_mapping_passes_literals_through() -> None:
    resolver = SecretResolver(env={"TOKEN": "abc"})
    out = resolver.resolve_mapping({"api_token": "env://TOKEN", "host": "db01", "port": 5432})
    assert out == {"api_token": "abc", "host": "db01", "port": 5432}


# --- scrubbing -------------------------------------------------------------


def test_scrub_masks_resolved_values() -> None:
    resolver = SecretResolver(env={"P": "topsecret"})
    resolver.resolve("env://P")
    masked = resolver.scrub("connecting with password=topsecret to db")
    assert "topsecret" not in masked
    assert "***" in masked


def test_scrub_noop_before_resolution() -> None:
    resolver = SecretResolver(env={})
    assert resolver.scrub("nothing to hide") == "nothing to hide"


# --- bao backend over a mock HTTP server -----------------------------------


class _MockBaoHandler(BaseHTTPRequestHandler):
    secrets = {"secret/data/prod/db": {"password": "bao-pw", "user": "svc"}}

    def log_message(self, *_args) -> None:  # silence test output
        return

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        token = self.headers.get("X-Vault-Token")
        if token != "test-token":
            self.send_response(403)
            self.end_headers()
            return
        path = self.path.lstrip("/").removeprefix("v1/")
        if path not in self.secrets:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"data": {"data": self.secrets[path]}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def mock_bao():
    server = HTTPServer(("127.0.0.1", 0), _MockBaoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}"
    server.shutdown()
    thread.join()


def test_bao_client_reads_kv2(mock_bao: str) -> None:
    client = BaoClient(addr=mock_bao, token="test-token")
    assert client.read_kv2("secret", "prod/db", "password") == "bao-pw"


def test_bao_client_missing_key_not_found(mock_bao: str) -> None:
    client = BaoClient(addr=mock_bao, token="test-token")
    with pytest.raises(SecretNotFoundError):
        client.read_kv2("secret", "prod/db", "absent")


def test_bao_client_bad_token_forbidden(mock_bao: str) -> None:
    client = BaoClient(addr=mock_bao, token="wrong")
    with pytest.raises(SecretForbiddenError):
        client.read_kv2("secret", "prod/db", "password")


def test_bao_client_missing_path_not_found(mock_bao: str) -> None:
    client = BaoClient(addr=mock_bao, token="test-token")
    with pytest.raises(SecretNotFoundError):
        client.read_kv2("secret", "prod/nope", "password")


def test_resolver_dispatches_bao(mock_bao: str) -> None:
    resolver = SecretResolver(bao_client_factory=lambda: BaoClient(addr=mock_bao, token="test-token"))
    assert resolver.resolve("bao://secret/prod/db#password") == "bao-pw"


# --- leak test: resolved values must never appear in on-disk artifacts ------


def test_resolved_secret_never_lands_in_scrubbed_artifact(tmp_path: Path) -> None:
    resolver = SecretResolver(env={"DB_PASSWORD": "leak-me-not"})
    secret = resolver.resolve("env://DB_PASSWORD")

    # Simulate command output + a run manifest that naively interpolated it.
    raw_log = f"$ psql 'password={secret}'\nconnected ok\n"
    raw_manifest = json.dumps({"cmd": f"export PGPASSWORD={secret}", "rc": 0})

    log_file = tmp_path / "host.log"
    manifest_file = tmp_path / "manifest.json"
    log_file.write_text(resolver.scrub(raw_log), encoding="utf-8")
    manifest_file.write_text(resolver.scrub(raw_manifest), encoding="utf-8")

    for artifact in (log_file, manifest_file):
        assert "leak-me-not" not in artifact.read_text(encoding="utf-8")
