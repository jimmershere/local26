# Security Policy

## Supported versions

Local-81 is pre-1.0. Security fixes are applied to the latest released
minor series only; older snapshots are not maintained.

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |
| < 0.1   | no        |

## Reporting a vulnerability

Please report security issues privately. **Do not open a public issue for a
suspected vulnerability.**

- Preferred: use GitHub's private vulnerability reporting on this repository
  (Security tab → "Report a vulnerability").
- Include: affected version/commit, a description of the impact, and the
  smallest set of steps or config needed to reproduce.

You can expect an initial acknowledgement within a few business days. Once a
fix is available it will be released and noted in `CHANGELOG.md`. Please give
us a reasonable window to remediate before any public disclosure.

## Scope notes

Local-81 is a push-based operator control plane that runs commands on remote
hosts over SSH. Reports that are especially in scope:

- Secret material written to plans, manifests, logs, or other on-disk artifacts.
- Command/argument injection in plan compilation or deploy execution.
- Access-policy or actor-check bypass in `deploy` / `compliance`.
- Privilege or path-traversal issues in rsync/ssh handling.
