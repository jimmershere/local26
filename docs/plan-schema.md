# SERAF Plan Schema v0.1

SERAF plans are deterministic execution artifacts. AI analysis is optional and advisory-only.

## Top-level structure

```json
{
  "schema": "seraf.plan.v0.1",
  "plan_id": "20260101T000000Z-abc123",
  "scope": "web",
  "created_at": "2026-01-01T00:00:00Z",
  "mode": "apply",
  "steps": [],
  "analysis": {
    "ai": {}
  }
}
```

## Required top-level keys

- `schema` (string): must be `seraf.plan.v0.1`
- `plan_id` (string): stable unique identifier
- `scope` (string): target scope
- `created_at` (UTC ISO8601 string)
- `mode` (string)
- `steps` (array): deterministic ordered execution steps

## Optional `analysis.ai` (advisory only)

`analysis.ai` is optional. When present, it must not alter deterministic execution semantics.

```json
{
  "analysis": {
    "ai": {
      "enabled": true,
      "provider": "example-provider",
      "model": "example-model",
      "generated_at": "2026-01-01T00:00:00Z",
      "risk": {
        "score": 0.74,
        "level": "high",
        "reasons": [
          "Large file churn on critical path",
          "Recent failure signature match"
        ]
      },
      "predicted_failures": [
        {
          "signature": "rsync-permission-denied",
          "likelihood": 0.62,
          "evidence": [
            "target path ownership drift",
            "prior run failure fingerprint"
          ],
          "recommended_checks": [
            "verify target path permissions",
            "run preflight write probe"
          ]
        }
      ],
      "policy": {
        "advisory_only": true,
        "may_block_deploy": false,
        "requires_human_ack_for_high_risk": true
      }
    }
  }
}
```

### `analysis.ai` fields

- `enabled` (bool)
- `provider` (string)
- `model` (string)
- `generated_at` (UTC ISO8601 string)
- `risk` (object)
  - `score` (number in range 0..1)
  - `level` (enum: `low`, `medium`, `high`)
  - `reasons` (array of strings)
- `predicted_failures` (array)
  - `signature` (string)
  - `likelihood` (number in range 0..1)
  - `evidence` (array of strings)
  - `recommended_checks` (array of strings)
- `policy` (object)
  - `advisory_only` (must be `true`)
  - `may_block_deploy` (must be `false`)
  - `requires_human_ack_for_high_risk` (bool)

## Determinism guarantee

`analysis.ai` must be treated as metadata only:

- MUST NOT mutate `steps`
- MUST NOT reorder operations
- MUST NOT change targeting, routing, or deploy eligibility on its own
- MUST remain advisory to human operators and downstream review workflows
