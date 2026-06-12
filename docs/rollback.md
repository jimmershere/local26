# Rollback & run GC

Local-81 already replays per-step `rollback` commands in LIFO order when a
deploy fails mid-run (`deploy --rollback-on-failure`). This page covers the
*after-the-fact* case: undoing a deploy that **succeeded** but turned out to be
wrong, plus garbage-collecting the run directories that accumulate over time.

## `local81 rollback RUN_ID`

Given the `run.json` of a completed run, Local-81 builds an ordered reverse plan
and — with `--execute` — applies it.

```bash
local81 rollback 20260612T101500Z-deploy            # show the plan
local81 rollback 20260612T101500Z-deploy --execute  # apply it
```

`RUN_ID` may be an exact run directory name or a unique prefix (the same
matching `local81 logs` and `local81 history` use).

### Honesty over magic

A step is reversed **only** when the run manifest recorded a concrete rollback
command for it. Today that means an rsync step deployed with scope backup
enabled, which records a `cp -a` restore from the `--backup` copy. Everything
else is surfaced as an explicit **skip with a reason**, never silently treated
as undone:

| Situation | Outcome |
| --- | --- |
| rsync step with a recorded backup | **restore** (reversed) |
| rsync step, scope backup disabled | skip — "no backup was recorded… cannot auto-restore" |
| step already converged (made no change) | skip — nothing to undo |
| step did not succeed (`rc != 0`) | skip — nothing to undo |
| step skipped during the run (`rc == -1`) | skip — nothing to undo |
| raw command / non-rsync step | skip — "no recorded reverse command" |

Reversible steps are applied in **LIFO order** (last deployed, first restored).

### What `--execute` writes

Applying a rollback creates a *new* run directory,
`.local81/runs/<timestamp>-rollback/`, containing a `rollback.json` record
(`schema: local81.rollback.v0.1`) with:

- `source_run_id` — the run that was reversed,
- `restored[]` — each restore command, its host, and its exit code,
- `skipped[]` — the non-rollbackable steps and why they were left untouched.

Artifacts stay owner-only (`0700` dir, `0600` file). The command's exit code is
non-zero if any restore command failed.

## `local81 gc`

Run directories under `.local81/runs/` accumulate forever otherwise. `gc`
enforces retention by **count** (keep the newest N) and/or **age** (drop
anything older than D days). Dry-run unless `--execute`.

```bash
local81 gc --keep 20                                  # preview
local81 gc --max-age-days 90                          # preview
local81 gc --keep 20 --max-age-days 90 --execute      # apply
```

With both bounds set a run survives only if it is within the newest `--keep`
*and* younger than `--max-age-days`. With neither bound supplied, nothing is
pruned and `gc` tells you so.
