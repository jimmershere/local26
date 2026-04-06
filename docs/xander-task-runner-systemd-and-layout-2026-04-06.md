# Xander Task Runner Systemd + Layout Notes

Updated: 2026-04-06

## Recommended install root on Xander

```text
/opt/xander-task-runner
```

## Directory layout

```text
/opt/xander-task-runner/
  tasks/
    inbox/
    running/
    done/
    failed/
  results/
  logs/
  src/
  pyproject.toml
```

## Why this layout

- keeps task state obvious
- allows atomic rename/move between queue states
- easy for humans to inspect
- easy for systemd service to own one working directory

## systemd service

Suggested unit file:
- `systemd/xander-task-runner.service`

Install flow on Xander:

```bash
sudo cp xander-task-runner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable xander-task-runner
sudo systemctl start xander-task-runner
sudo systemctl status xander-task-runner
```

## Notes

- sequential processing only in phase 1
- later, if needed, support multiple workers explicitly rather than implicitly
- if `floor2` user is not correct for final install, update `User=` and `Group=` accordingly
