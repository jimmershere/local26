# Seraf Phase 1 Progress — 2026-04-06

## Summary

Real Python migration progress is now in place for the Seraf control plane.
This was built and exercised through the bounded `project_task` / Xander Task Runner path, not by hand-waving.

## Completed

### Python scaffold
- `pyproject.toml`
- `src/seraf/`
- initial package structure

### Runtime primitives
- `src/seraf/models.py`
- `src/seraf/paths.py`
- `src/seraf/runner.py`

### Migrated Python commands
- `doctor`
- `status`
- `plan`

### Tests
- Python-native tests added for:
  - runner
  - paths
  - doctor
  - status
- Existing shell tests preserved
- `plan` shell parity tests now passing:
  - `tests/test_plan.sh`
  - `tests/test_plan_summary.sh`

## Important implementation notes

- `bin/seraf` now prefers Python for migrated commands while non-migrated commands can still remain on the shell path.
- `plan` required bounded parity recovery work for:
  - scope detection (`[tools]` was incorrectly emitted as a deploy scope)
  - shell-expected escaped quoting in mkdir / rollback commands
- Test execution was normalized via project-local `.venv` to avoid mutating global Python.

## Xander Task Runner progress

Separate repo created:
- `/home/jimmer/projects/xander-task-runner`

Current runner capabilities:
- file-backed queue
- strict `project_task` structure
- bounded command-plan executor
- result JSON output
- markdown progress summary output
- real sequential execution against Seraf tasks

## Current phase-1 command status

- `doctor` ✅
- `status` ✅
- `plan` ✅
- `deploy` not migrated yet

## Recommended next steps

1. Commit current Seraf state cleanly
2. Commit current Xander Task Runner state cleanly
3. Decide next migration target deliberately:
   - `deploy` for the big move
   - or a lower-risk support command first
