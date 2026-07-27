# Node Scraper documentation

Documentation index for **amd-node-scraper**. Start with [architecture/overview.md](architecture/overview.md) if you are new to the codebase or want to see how the CLI reaches plugins, connections, and events.

## Architecture

| Document | Description |
| --- | --- |
| [architecture/overview.md](architecture/overview.md) | End-to-end flow: CLI → executor → plugins → connections → logs |
| [architecture/events-and-results.md](architecture/events-and-results.md) | How events are created, aggregated, and written to run logs |

## CLI and configuration

| Document | Description |
| --- | --- |
| [cli/subcommands.md](cli/subcommands.md) | All CLI subcommands with examples |
| [cli/configs.md](cli/configs.md) | Plugin configs, global args, reference configs |

## Connections (in-band and out-of-band)

| Document | Description |
| --- | --- |
| [connections/overview.md](connections/overview.md) | In-band vs OOB patterns, base classes, when to use each |
| [connections/connection-config.md](connections/connection-config.md) | `connection-config.json` examples (SSH, Redfish) |

## Plugins

| Document | Description |
| --- | --- |
| [PLUGIN_DOC.md](PLUGIN_DOC.md) | Generated catalog of every built-in plugin, collector, analyzer, and command |
| [plugins/inband.md](plugins/inband.md) | In-band plugin authoring patterns |
| [plugins/oob.md](plugins/oob.md) | Out-of-band (Redfish / BMC SSH) plugin patterns |
| [node-scraper-external/README.md](node-scraper-external/README.md) | External plugin package example |
| [../EXTENDING.md](../EXTENDING.md) | Programmatic integration and external plugins |
| [../README_SERVICEABILITY.md](../README_SERVICEABILITY.md) | Serviceability plugin setup and run guide |

## Other

| Document | Description |
| --- | --- |
| [../README.md](../README.md) | Project overview, install, quick start |
