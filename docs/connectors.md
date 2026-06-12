# Connectors

A **connector** is the single interface the fact, op, and resolve layers use to
reach a target. It is Local-81's version of pyinfra's connector index: SSH/rsync
is *one* implementation, not the architecture. Facts probe a target and ops
converge it without ever importing a concrete connector class — they depend only
on the `Connector` protocol.

## The protocol

`src/local81/connectors.py` defines `Connector` as a `typing.Protocol` with a
deliberately tiny surface:

| Method | Purpose |
| --- | --- |
| `run(command, *, timeout_seconds=None, env=None)` | Execute a command, return a `CommandResult`. |
| `put(local_path, remote_path, *, recursive=False)` | Move a file or directory **to** the target. |
| `get(remote_path, local_path, *, recursive=False)` | Move a file or directory **from** the target. |
| `close()` | Release any held resource (sockets, sessions). |

`run` must be side-effect-free with respect to target state — idempotency and
change decisions live in the ops layer; facts call `run` only for read-only
probes.

## Built-in connectors

| Target form | Connector | Transport |
| --- | --- | --- |
| `@local`, `local`, or `None` | `LocalConnector` | `subprocess` + `shutil` on the control node |
| `@docker/<container>` | `DockerConnector` | `docker exec` / `docker cp` |
| anything else (a hostname) | `SshConnector` | SSH for `run`, `rsync` for `put`/`get` |

`LocalConnector` makes localhost a first-class target, so facts and ops are
testable without SSH fixtures. `DockerConnector` shells into a local container.
`SshConnector` is the production default.

## Inventory routing

`connector_for_target(target, *, rsync_opts="-az")` maps an inventory string to a
connector:

```python
connector_for_target(None)            # -> LocalConnector
connector_for_target("@local")        # -> LocalConnector
connector_for_target("@docker/web")   # -> DockerConnector(container="web")
connector_for_target("db01.host")     # -> SshConnector(host="db01.host")
```

`resolve.connector_for_host` delegates to this resolver, so the deploy probe gate
routes `@docker/<name>` steps through `docker exec` automatically.

## Writing your own connector

A new connector is implementable against the four-method surface alone — you do
not touch `facts/`, `ops/`, or `resolve.py`. Implement the protocol, return
`CommandResult`s, and you can pass an instance straight into
`resolve_step_action(step, connector=...)`:

```python
class MyConnector:
    name = "@mine"

    def run(self, command, *, timeout_seconds=None, env=None):
        ...  # return a CommandResult

    def put(self, local_path, remote_path, *, recursive=False):
        ...

    def get(self, remote_path, local_path, *, recursive=False):
        ...

    def close(self):
        return None
```

`isinstance(MyConnector(), Connector)` is `True` because `Connector` is a
`runtime_checkable` protocol. The test suite proves this contract with a toy
`EchoConnector` (`tests/test_python_connectors.py`) that satisfies the protocol
and drives `resolve_step_action` without any real target — if that ever stops
working, the connector surface has grown a hidden dependency.
