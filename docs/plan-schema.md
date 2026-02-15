# SERAF Plan Schema v0.1

## Top-level required keys

```json
{
  "seraf_version": "0.1",
  "kind": "plan",
  "mode": "deploy",
  "schema": "seraf.plan.v0.1",
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
