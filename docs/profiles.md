# Local-26 profiles

Profiles let you override base `.local26/config.ini` settings per environment.

## Use a profile

```bash
local26 --profile prod deploy --plan .local26/plans/latest.plan.json
local26 --profile staging doctor
```

Local-26 loads `.local26/profiles/<name>.yaml` and merges it over the base config.

## List profiles

```bash
local26 profiles
```

## Create a profile

```bash
local26 profile create prod
```

## Profile format

```yaml
local26:
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
- Profile validation is included in `local26 doctor`.
