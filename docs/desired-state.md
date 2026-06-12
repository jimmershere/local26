# Desired-state convergence (v2 plans)

Local-81 v2 plans describe each file and directory step twice over: the legacy
**executable** view (`type`, `host`, `cmd`, `rollback`) that the runner has always
used, and a **desired-state** view (`op` + `intent`) that says what the target
should look like once the step has run. The two are kept deliberately redundant
so the executor, policy scanner, and rollback machinery need no changes — the
desired-state metadata is purely additive.

At apply time `deploy` uses the desired-state view to **skip work that is already
done**. This is the pyinfra facts→operations pattern: read a read-only *fact* from
the live target, *diff* it against the *intent*, and run the placement command
only when they disagree.

## How a step is gated

For each step on a real (`--execute`) run, before running `cmd`:

1. **Opt-in.** If the step has no `op`/`intent`, it is a raw command — run it as
   before. (`resolve_step_action` returns `(None, None)`.)
2. **Probe.** Gather the live fact through a `Connector` — `LocalConnector` for
   `@local` hosts, `SshConnector` otherwise. File facts include existence and a
   `sha256` of the current bytes; directory facts include existence.
3. **Diff.** Compare the fact to the intent via the ops layer:
   - `file.synced`: target missing → `create`; present but `sha256` differs →
     `update`; bytes already match → `none`.
   - `dir.present`: directory missing → `create`; present → `none`.
4. **Act.** `none` → record the step as `converged` (rc 0) and **do not run
   `cmd`**. `create`/`update`/`unknown` → run `cmd` exactly as a v1 plan would.

The chosen action and the observed state are written into the run record
(`steps[].action`, `steps[].observed_state`, `steps[].converged`) so operators can
see *why* a step ran or was skipped.

## Two safety properties

- **Opt-in** — steps without desired-state metadata are never gated, so raw
  command plans and `local81.plan.v0.1` plans behave identically to before.
- **Fail-open** — any probe error (SSH failure, unreadable target, missing tool)
  resolves to `unknown`, which runs the `cmd`. The gate can only ever *skip* work
  it has positively proven converged; a flaky probe never hides a needed change.

## Convergence and drift

Because the gate compares baked-in intent against the live target, two useful
properties fall out for free:

- **Convergence (double-apply).** Deploy a plan, then deploy it again: the second
  pass observes matching `sha256`s, reports `action=none` for every file step, and
  ships nothing.
- **Drift guard.** If a target is hand-edited after a converged deploy, the next
  run observes the changed `sha256`, reports `update`, and re-runs the placement
  command — restoring the desired bytes.

## `deploy --check` drift guard

`deploy --check` validates the plan structurally and then, for v2 plans, runs the
same fact-gathering pass deploy would. It classifies each op-step:

- `converged` — target already matches intent.
- `create` — target absent; a normal first apply, not drift.
- `drift` — target exists but its content diverges from the plan's desired state.
- `unprobed` — the probe could not run (e.g. SSH unreachable); fail-open warning.

A `drift` step makes `--check` **fail** by default, so a stale plan or a
hand-edited target is caught before deploy. `--allow-drift` downgrades drift to a
warning when the divergence is expected (deploy will reconcile it anyway).

## Where it lives

- `src/local81/facts/` — read-only probes (`file_state`, `dir_state`, …) and fact
  models.
- `src/local81/ops/` — desired-state intents and the pure `diff(fact, intent)`
  operations that return an action + commands.
- `src/local81/resolve.py` — `resolve_step_action(step)` wires a step's `op`/
  `intent` to the right probe and diff, with the opt-in / fail-open contract.
- `src/local81/commands/deploy.py` — calls the resolver in `_run_step` and skips
  converged steps.
