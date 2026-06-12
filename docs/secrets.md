# Secrets

Local-81 never stores secret *literals*. Config and plans hold **references**;
the plaintext is fetched on demand at the control node and exists only in
memory. This is the on-disk half of the "secrets never at rest" guardrail.

## Reference syntax

A secret reference is a `scheme://` string. Three schemes are understood:

| Scheme  | Form                                  | Resolves to |
|---------|---------------------------------------|-------------|
| `env`   | `env://VAR_NAME`                      | the contents of the named environment variable on the control node |
| `bao`   | `bao://<mount>/<path>#<key>`          | a field of an OpenBao / Vault **KV v2** secret |
| `sops`  | `sops://<file>#<dotted.json.path>`    | a value decrypted on demand from a SOPS file |

Examples:

```
env://DB_PASSWORD
bao://secret/prod/db#password
sops://secrets.enc.json#db.password
```

Anything *without* a `scheme://` prefix is treated as a literal and rejected —
a bare value where a reference is expected is an operator mistake surfaced
immediately, never leaked.

## Where references are accepted

Database targets accept references on `*_ref` keys (alongside the existing
`*_env` / `*_file` indirection). A `*_ref` value that looks like a managed
reference (`scheme://...`) is **syntax-checked at config load** — a typo in a
`bao://`/`sops://`/`env://` ref fails fast at `doctor` / config validation,
not at apply time. A plain `*_ref` value (e.g. an external service name) is
left untouched.

```ini
[database "prod"]
engine = postgres17
host = db01
service_ref = bao://secret/prod/db#password
```

## OpenBao / Vault

The KV v2 read client is stdlib-only (no `hvac` dependency). Configuration is by
environment variable on the control node:

| Variable | Purpose |
|----------|---------|
| `BAO_ADDR` / `VAULT_ADDR` | server address (default `http://127.0.0.1:8200`) |
| `BAO_TOKEN` / `VAULT_TOKEN` | auth token (preferred) |
| `BAO_ROLE_ID` + `BAO_SECRET_ID` | AppRole login fallback |
| `BAO_SKIP_VERIFY` | set to `1`/`true` to disable TLS verification (loud opt-out only) |

TLS verification is **on by default**. A `403` becomes a *forbidden* error and a
`404`/missing key becomes a *not found* error — both fail fast rather than
injecting an empty value.

## SOPS

`sops://` references shell out to the `sops` binary (which must be on `PATH`),
decrypt to JSON, and walk the dotted key path. Local-81 never re-implements the
crypto; the decrypted plaintext only lives in memory.

## Scrubbing

The resolver remembers every value it hands out and can mask those exact strings
out of command output, host logs, and run manifests before they are written —
so a secret that flows through a command never lands on disk in cleartext.

## Doctor

`local81 doctor` reports a `secrets:refs` line counting the managed references
in your db config and confirming they parse. A malformed reference shows up as a
blocking `[FAIL]`.
