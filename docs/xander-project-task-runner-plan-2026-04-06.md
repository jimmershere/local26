# Xander Project Task Runner Plan

Updated: 2026-04-06
Status: ready-to-build design
Scope: minimal structured work intake/runtime for Xander before native OpenClaw attachment

## Purpose

Give Xander (`floor2`) a bounded, inspectable way to accept structured engineering work as `project_task` jobs.

This is intentionally **not** a fake full agent protocol.
It is a thin execution contract for real project work.

Primary first customer:
- **Local-81** at `/app/giles/local81`

---

## Why this should exist outside Local-81 command logic

Local-81 is the **project being worked on**.
Xander Task Runner is the **execution substrate** for bounded project work.

That separation keeps things cleaner:
- Local-81 remains a target repo and product
- Xander runner handles intake, validation, queueing, execution, and summaries
- later, Local-81 can emit `project_task` jobs if useful

---

## Recommended phase-1 design

### Runtime style
Use a **native Python service** on Xander, managed by `systemd`.

Why:
- consistent with other native services already on Xander (`ollama`, likely `ComfyUI`)
- simpler than full containerization for first pass
- easier to inspect and debug
- low token / low API usage

### Queue style
Use a **file-backed queue** first.

Why:
- trivial to inspect
- no RabbitMQ dependency for day one
- good enough for sequential work
- easier to recover manually when something goes sideways

---

## Proposed repo layout

This can live as its own small project, or later be folded into a broader worker runtime.

```text
xander-task-runner/
  README.md
  pyproject.toml
  src/xander_task_runner/
    __init__.py
    cli.py
    models.py
    validator.py
    paths.py
    queue.py
    executor.py
    summary.py
    timestamps.py
  tasks/
    inbox/
    running/
    done/
    failed/
  results/
  logs/
  systemd/
    xander-task-runner.service
```

---

## Module responsibilities

### `models.py`
Define typed dataclasses for:
- `ProjectTask`
- `TaskSummary`
- `TaskResult`

Keep them boring and JSON-friendly.

### `validator.py`
Responsibilities:
- validate JSON shape against the `project_task` contract
- reject missing required fields
- reject unknown `task_type`
- optionally validate against `docs/project-task-schema.json`

### `paths.py`
Responsibilities:
- centralize queue/result/log directory paths
- create directories if missing
- avoid hardcoded path soup

### `queue.py`
Responsibilities:
- enqueue task file
- list pending/running/completed jobs
- atomically move task files between states:
  - `inbox -> running -> done|failed`

### `executor.py`
Responsibilities:
- load one validated task
- mark `started_at`
- run bounded work in `repo_path`
- enforce `max_runtime_minutes`
- capture high-level outputs
- mark `finished_at`
- write result JSON

### `summary.py`
Responsibilities:
- normalize final summary shape
- append or write `write_summary_to` markdown when configured
- preserve concise structured result JSON

### `cli.py`
Suggested commands:
- `enqueue <task.json>`
- `run-once`
- `run-loop`
- `status`
- `show <task-id>`

---

## Execution contract

Phase 1 meaning of `project_task`:
- work only inside `repo_path`
- read listed `docs` first
- operate only on stated `objective` and `tasks`
- respect `constraints`
- stop at `stop_condition`
- emit summary even if partially complete

This makes the task bounded and reviewable.

---

## Status lifecycle

```text
pending -> running -> done
pending -> running -> failed
```

Required timestamps:
- `created_at`
- `started_at`
- `finished_at`

---

## Result contract

Minimal required shape:

```json
{
  "status": "done",
  "started_at": "2026-04-06T14:00:00Z",
  "finished_at": "2026-04-06T14:22:00Z",
  "summary": {
    "files_changed": [],
    "commands_working": [],
    "tests_passed": [],
    "tests_failed": [],
    "open_questions": [],
    "recommended_next_job": ""
  }
}
```

This is intentionally small.

---

## Suggested on-disk queue paths

On Xander, recommended root:

```text
/opt/xander-task-runner/
```

Suggested subdirs:

```text
/opt/xander-task-runner/tasks/inbox
/opt/xander-task-runner/tasks/running
/opt/xander-task-runner/tasks/done
/opt/xander-task-runner/tasks/failed
/opt/xander-task-runner/results
/opt/xander-task-runner/logs
```

---

## Suggested systemd unit

Service name:
- `xander-task-runner.service`

Execution model:
- long-running process using `run-loop`
- sequential processing only in phase 1

Why sequential first:
- simpler failure model
- easier summaries
- avoids Xander going feral with overlapping tasks
- matches current desired Local-81 chain

---

## Interaction with Local-81

Initial use case is the four-job Local-81 phase-1 chain:

1. scaffold
2. runner / models / paths
3. doctor
4. tests

These should run one at a time, using the exact bounded job structure already drafted.

---

## Future phase-2 upgrades

After phase 1 works reliably:
- dependency enforcement with `depends_on`
- retry policy
- task cancellation
- JSON schema validation in runtime
- optional HTTP API
- optional RabbitMQ intake
- richer result artifacts
- later, OpenClaw-native attachment for Xander

---

## Guardrails

Do:
- keep queue mechanics inspectable
- prefer atomic file moves
- keep summary contract small and stable
- preserve all original task metadata
- log enough to debug failures

Do not:
- invent agent magic
- hide execution decisions
- allow unbounded repo-wide action without explicit task scope
- parallelize phase-1 by default

---

## Bottom line

`project_task` should start as a **small native file-backed work runner on Xander**.
That gets structured work flowing now, with minimal API cost and minimal system complexity.
