# CLI subcommands

Default subcommand when omitted: **`run-plugins`**.

Global flags apply to all subcommands: `--sys-name`, `--sys-location`, `--sys-interaction-level`, `--plugin-configs`, `--connection-config`, `--log-path`, `--log-level`, `--no-console-log`, `--gen-reference-config`, `--skip-sudo`. Run `node-scraper -h` for the full list.

Plugins can be specified via **`--plugin-configs`** JSON and/or **`run-plugins`** on the same command.

## `run-plugins`

Run one or more plugins with optional per-plugin arguments.

```sh
node-scraper run-plugins <PluginName> [-h] [plugin args...]
```

Plugin-specific help:

```sh
node-scraper run-plugins BiosPlugin -h
```

Examples:

```sh
node-scraper run-plugins BiosPlugin --exp-bios-version TestBios123
node-scraper run-plugins BiosPlugin RocmPlugin
node-scraper --plugin-configs=NodeStatus run-plugins PciePlugin
node-scraper --connection-config redfish.json run-plugins RedfishEndpointPlugin
```

Offline analysis (skip collection):

```sh
node-scraper run-plugins DmesgPlugin --data /path/to/dmesg.log --collection False
```

## `describe`

Inspect built-in configs or plugins.

```sh
node-scraper describe config
node-scraper describe config <config-name>
node-scraper describe plugin
node-scraper describe plugin <plugin-name>
```

## `gen-plugin-config`

Generate a starter plugin JSON config with defaults filled in.

```sh
node-scraper gen-plugin-config --plugins DmesgPlugin
node-scraper gen-plugin-config --gen-reference-config-from-logs scraper_logs_<path>/ --output-path custom_output_dir
```

## `compare-runs`

Diff data models between two run log directories.

```sh
node-scraper compare-runs <path1> <path2>
node-scraper compare-runs path1 path2 --skip-plugins SomePlugin
node-scraper compare-runs path1 path2 --include-plugins DmesgPlugin
node-scraper compare-runs path1 path2 --include-plugins DmesgPlugin --dont-truncate
```

## `summary`

Aggregate multiple run `nodescraper.csv` files into one `summary.csv`.

```sh
node-scraper summary --search-path /<path_to_scraper_logs>
```

## `show-redfish-oem-allowable`

Query BMC OEM diagnostic allowable types (requires Redfish connection config). Use output to populate `oem_diagnostic_types_allowable` in Redfish OEM diag plugin configs.

```sh
node-scraper --connection-config connection-config.json \
  show-redfish-oem-allowable \
  --log-service-path "redfish/v1/Systems/UBB/LogServices/DiagLogs"
```

See [../plugins/oob.md](../plugins/oob.md) for Redfish OEM diag and endpoint plugin examples.

## Related

- [configs.md](configs.md) — plugin JSON structure, built-in configs, reference configs
- [../connections/connection-config.md](../connections/connection-config.md) — connection JSON
- [../architecture/overview.md](../architecture/overview.md) — how the CLI drives plugins
