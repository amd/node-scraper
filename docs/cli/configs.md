# Plugin and run configs

## Plugin config structure

A plugin JSON config follows the `PluginConfig` model:

```json
{
  "name": "optional human name",
  "desc": "optional description",
  "global_args": {},
  "plugins": {
    "BiosPlugin": {
      "collection": true,
      "analysis": true,
      "analysis_args": {
        "exp_bios_version": "TestBios123"
      }
    }
  },
  "result_collators": {}
}
```

- **`global_args`** — key/value pairs passed to plugins that support them (e.g. skip sudo, disable analysis).
- **`plugins`** — map of plugin name → arguments (`collection_args`, `analysis_args`, `collection`, `analysis`, `data`, etc.).
- **`result_collators`** — optional; CLI adds `TableSummary` by default.

## Global args example

Skip sudo-requiring plugins and disable analysis:

```json
{
  "global_args": {
    "collection_args": { "skip_sudo": 1 },
    "collection": 1,
    "analysis": 0
  },
  "plugins": { },
  "result_collators": {}
}
```

## `--plugin-configs`

Comma-separated built-in names and/or paths:

```sh
node-scraper --plugin-configs=NodeStatus run-plugins PciePlugin
node-scraper --plugin-configs=plugin_config.json
```

Built-in configs:

| Name | Purpose |
| --- | --- |
| **NodeStatus** | Subset of common health plugins |
| **AllPlugins** | Every registered plugin with defaults (reference / full sweep) |

## Reference config (`--gen-reference-config`)

Capture current system values into `reference_config.json`:

```sh
node-scraper --gen-reference-config run-plugins BiosPlugin OsPlugin
node-scraper --plugin-configs=AllPlugins --gen-reference-config
```

Use the generated file on another system for comparison:

```sh
node-scraper --plugin-configs=reference_config.json
```

## Dmesg custom regex example

```json
{
  "global_args": {},
  "plugins": {
    "DmesgPlugin": {
      "analysis_args": {
        "check_unknown_dmesg_errors": false,
        "interval_to_collapse_event": 60,
        "num_timestamps": 3,
        "error_regex": [
          {
            "regex": "MY_CUSTOM_ERROR.*",
            "message": "My Custom Error Detected",
            "event_category": "SW_DRIVER",
            "event_priority": 3
          }
        ],
        "priority_override_rules": [
          { "message": "Application Crash", "new_priority": "ERROR" }
        ]
      }
    }
  },
  "result_collators": {}
}
```

```sh
node-scraper --plugin-configs=dmesg_custom_config.json run-plugins DmesgPlugin
```

## Related

- [subcommands.md](subcommands.md) — CLI commands
- [../PLUGIN_DOC.md](../PLUGIN_DOC.md) — per-plugin argument reference
