# Local-81 profiles

Profiles let you override base `.local81/config.ini` settings per environment.

## Use a profile

```bash
local81 --profile prod deploy --plan .local81/plans/latest.plan.json
local81 --profile staging doctor
```

Local-81 loads `.local81/profiles/<name>.yaml` and merges it over the base config.

## List profiles

```bash
local81 profiles
```

## Create a profile

```bash
local81 profile create prod
```

## Profile format

```yaml
local81:
  profile: prod
defaults:
  rsync_opts: -aP
notifications:
  notify_on_success: true
scopes:
  web:
    target_dir: /srv/prod/app
    servers: [prod1, prod2]
```

## Notes

- Top-level maps merge with the base config.
- `scopes` entries merge by scope name.
- Profile validation is included in `local81 doctor`.
