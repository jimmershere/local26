# LOCAL-81 Plan Schema v2

`plan` emits `schema: "local81.plan.v2"`. v2 plans are a superset of the legacy
`local81.plan.v0.1` format: every executable field (`type`, `host`, `cmd`,
`local_path`/`remote_path`, `rollback`, `checks`) is unchanged, so the executor,
policy, and rollback machinery read a v2 plan exactly as before. What v2 adds is
**desired-state metadata** on file and directory steps — an `op` and an `intent`
— which lets `deploy` skip steps it can prove are already converged. See
[desired-state.md](desired-state.md) for the convergence model and
[schemas/plan.v2.schema.json](schemas/plan.v2.schema.json) for the JSON Schema.

`deploy --check` and `doctor` still accept `local81.plan.v0.1` plans, so existing
plans keep working untouched.

## Top-level required keys

```json
{
  "local81_version": "0.1",
  "kind": "plan",
  "mode": "deploy",
  "schema": "local81.plan.v2",
  "plan_id": "20260101T000000Z-abc123",
  "created_at": "2026-01-01T00:00:00Z",
  "config_fingerprint": "sha256:<hex>",
  "scopes": []
}
```

## Scope object

Each `scopes[]` entry contains:

- `scope`
- `inputs` with `source_dir`, `target_dir`, `servers`, `rsync_opts`, `backup`, `backup_suffix`, `remote_mkdir`
- `discovery` with `strategy`, `since` (nullable), `files_found`, `files_selected`
- `routing` with `env_from_filename_prefix`, `env_from_server_name_char_at`, `env_from_server_name_char_map`
- `steps`
- `summary.counts` with `mkdir_steps`, `rsync_steps`, `rollbackable_steps`, `warnings`

## Step object

- `id`: `scope:<scope>:<nnnn>` (stable per-scope numbering)
- `type`: `mkdir` or `rsync`
- `host`
- `cmd`
- `local_path` / `remote_path` for `rsync`
- `rollback`: `null` or `{type, cmd}`
- `checks.requires`: `["ssh"]` or `["ssh","rsync"]`

### v2 desired-state fields (optional, per step)

File and directory steps carry an `op` and an `intent` describing the converged
target. These are advisory to the executor: at apply time `deploy` probes the
live target and runs the step's `cmd` only when the observed state diverges from
the intent. A step with no `op`/`intent` is a raw command and always runs.

- `rsync` steps: `op = "file.synced"`, `intent = {path, sha256[, mode, owner, group]}`.
  `intent.path` equals `remote_path`; `intent.sha256` is the 64-hex digest of the
  desired source bytes, baked in at plan time.
- `mkdir` steps: `op = "dir.present"`, `intent = {path[, mode, owner, group]}`.

The gate is **opt-in** (no metadata → run as before) and **fail-open** (any probe
error → run the `cmd`); it can only skip work it has positively proven converged,
never hide a needed change.

## Deterministic ordering

- scopes: config order
- servers: config order
- files: sorted by relative path
- steps per scope/server: mkdir (unique remote dirs sorted), then rsync (files sorted)

## Optional `analysis.ai`

```json
{
  "analysis": {
    "ai": {
      "enabled": false,
      "provider": null,
      "model": null,
      "generated_at": null,
      "risk": { "score": null, "level": null, "reasons": [] },
      "predicted_failures": [],
      "policy": {
        "advisory_only": true,
        "may_block_deploy": false,
        "requires_human_ack_for_high_risk": true
      }
    }
  }
}
```

## Plan integrity and approval gates

Generated plans include `config_fingerprint`, a `sha256:<64 lowercase hex>` digest of the config file used to build the plan. `local81 deploy --check` treats missing, malformed, or stale fingerprint metadata as warnings so operators can identify plans generated from older config without changing live deploy behavior.

Approval-gate enforcement needs a product decision before it can become blocking deploy behavior. A future approval model should define who can approve a plan, what exact plan/config fingerprint is approved, how approvals expire, and whether emergency deploys can bypass the gate. Until those decisions are made, integrity diagnostics should remain advisory outside `deploy --check` validation.
