# Scheduling & triggers

Local-81 is push-based and runs **no daemon**. To run a command on a schedule it
does not install or own a scheduler — instead `local81 schedule add` renders a
plain **systemd** `.service` + `.timer` pair (plus a `flock` wrapper) into
`.local81/schedules/` for you to install. Every artifact is human-greppable and
you stay in control of the live system: honesty over magic.

## Quick start

```bash
local81 schedule add nightly \
    --command "local81 deploy --latest --execute" \
    --on-calendar "*-*-* 02:00:00" \
    --notify-url "https://n8n.example/webhook/deploy-done"
```

This writes four files under `.local81/schedules/`:

| File | Purpose |
|------|---------|
| `nightly.json` | the schedule definition (owner-only `0600`) |
| `systemd/local81-nightly.sh` | wrapper: runs the command under `flock -n` |
| `systemd/local81-nightly.service` | `Type=oneshot` unit calling the wrapper |
| `systemd/local81-nightly.timer` | `OnCalendar` timer, `Persistent=true` |

Then install as root on the control node (the command prints this hint):

```bash
sudo cp .local81/schedules/systemd/local81-nightly.service \
        .local81/schedules/systemd/local81-nightly.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now local81-nightly.timer
systemctl list-timers local81-nightly.timer
```

## No overlapping runs

The rendered wrapper is:

```sh
#!/bin/sh
set -eu
exec flock -n /…/.local81/schedules/nightly.lock local81 deploy --latest --execute
```

`flock -n` takes the lock non-blocking: if a previous run is still going when the
next timer fires, the new invocation exits immediately rather than stacking a
second concurrent deploy. The behaviour is visible in the file, not hidden.

## `OnCalendar`

`--on-calendar` is passed straight through to systemd. Common forms:

| Spec | Meaning |
|------|---------|
| `daily` | 00:00 every day |
| `*-*-* 02:00:00` | 02:00 every day |
| `Mon *-*-* 06:00:00` | 06:00 every Monday |
| `*-*-01 03:00:00` | 03:00 on the 1st of each month |

Local-81 validates that the value is non-empty and free of shell
metacharacters; systemd owns the full grammar. Check a real spec with
`systemd-analyze calendar "<spec>"`.

## Notifying n8n (or any webhook)

With `--notify-url`, the service unit gets a best-effort `ExecStartPost`:

```ini
ExecStartPost=/bin/sh -c 'curl -fsS -m 10 -X POST \
  -H "Content-Type: application/json" \
  -d "{\"schedule\":\"nightly\",\"status\":\"done\"}" \
  https://n8n.example/webhook/deploy-done || true'
```

The trailing `|| true` means a down webhook never fails the run. In **n8n**, add
a **Webhook** node (HTTP POST) whose path matches the URL; it receives
`{ "schedule": "<name>", "status": "done" }` and can fan out to Slack, a ticket,
or a follow-up workflow. Because it is a plain `curl`, any inbound-webhook tool
works the same way.

## Doctor

```bash
local81 schedule doctor
```

Reports whether `systemctl` and `flock` are present on this host and validates
every defined schedule (name, calendar, notify URL). A malformed schedule is a
blocking `[FAIL]`.

## Removing a schedule

```bash
local81 schedule remove nightly
```

This deletes the definition and rendered files. If you already installed the
units, the command reminds you to disable and remove them from
`/etc/systemd/system`.
