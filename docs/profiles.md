# Seraf profiles

Profiles let you override base `.seraf/config.ini` settings per environment.

## Use a profile

```bash
seraf --profile prod deploy --plan .seraf/plans/latest.plan.json
seraf --profile staging doctor
```

Seraf loads `.seraf/profiles/<name>.yaml` and merges it over the base config.

## List profiles

```bash
seraf profiles
```

## Create a profile

```bash
seraf profile create prod
```

## Profile format

```yaml
seraf:
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
- Profile validation is included in `seraf doctor`.
