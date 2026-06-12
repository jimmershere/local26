# Fleet execution

`local81 deploy` runs a plan across many hosts with **rolling batches** and a
**failure threshold** — pyinfra's `changed / no-change / failed` summary taxonomy
with Semaphore-style rolling-update ergonomics. It is stdlib-only
(`concurrent.futures.ThreadPoolExecutor`), tuned for the 10–500 host, I/O-bound
SSH scale Local-81 targets; there is no gevent/asyncio rewrite.

## Activating fleet mode

Fleet mode is **opt-in**: it turns on when any of `--forks`, `--serial`,
`--max-fail`, or `--limit` is passed. The fleet is the set of distinct `host`
values across the plan's steps. Without these flags, deploy behaves exactly as
before (single-scope local execution, or `--hosts-file` grouping).

| Flag | Meaning | Default |
| --- | --- | --- |
| `--forks N` | Max hosts executing **concurrently within a batch**. | 5 |
| `--serial N` / `N%` | Rolling **batch size**; batches run one after another. | one batch (all hosts) |
| `--max-fail N` / `N%` | Abort new batches once cumulative failures reach this. | 0 (first failure stops new batches) |
| `--limit GLOB` | Restrict the fleet to hosts matching a glob (`web*`, `db?`). | all hosts |

Percentages round **up**: `--serial 50%` of 3 hosts is 2, so a rolling batch
never silently shrinks to a trickle.

## Batch semantics

```
fleet = [h0 h1 h2 h3 h4 h5 h6 h7 h8 h9]   --serial 3  --forks 3  --max-fail 1

 batch 1: [h0 h1 h2]   <- up to 3 run at once
 batch 2: [h3 h4 h5]
 batch 3: [h6 h7 h8]
 batch 4: [h9]
```

Batch *N+1* starts only if the failure threshold has not been breached across
batches *1..N*. If `h1` fails in batch 1, `--max-fail 1` is reached: in-flight
hosts in batch 1 finish, then batches 2–4 are **skipped** — `h3..h9` are recorded
as `skipped`, never touched. This is the "stop if too many fail" guardrail.

## Summary taxonomy

Every host lands in exactly one terminal state; `ok` is the roll-up of the two
success states:

| Status | Meaning |
| --- | --- |
| `changed` | Ran; at least one file step actually pushed (drifted/new). |
| `unchanged` | Ran; every op-step was already converged — a no-op (see [desired-state](desired-state.md)). |
| `failed` | A step exited non-zero (or the host's connector crashed). |
| `skipped` | Never started: the failure threshold aborted its batch. |
| `ok` | `changed + unchanged` — ran without failing. |

The summary table prints at the end of the run, and the run manifest
(`.local81/runs/<run-id>/run.json`) is the source of truth: its `hosts` array
carries each host's `status`, `rc`, and `deployed_files`.

## Per-host logs

Each host's step results are written to `.local81/runs/<run-id>/<host>.log`
(owner-only, `0600`). Read one host's log with:

```bash
local81 logs <run-id> --host web1
```

`local81 logs <run-id>` (no `--host`) still renders the whole-run view.

## Convergence interplay

Fleet mode composes with the v2 desired-state gate: each host's op-steps are
probed and skipped when already converged, so a re-run of a fully-converged fleet
reports every host `unchanged` and pushes nothing — convergence holds per host,
in parallel.
