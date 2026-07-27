# ServiceabilityPluginMI3XX

**ServiceabilityPluginMI3XX** is an out-of-band Redfish plugin. It collects BMC event log entries (and optional firmware inventory), builds AFID events, and can run an external Python **service hub** for recommendations.

For the full argument list and generated plugin table entry, see [PLUGIN_DOC.md](../PLUGIN_DOC.md).

## What it does

1. **Collect** — Redfish GET on the configured event log `Entries` collection (`collection_args.rf_event_log_uri`), with optional pagination, time filters, CPER attachment fetch, assembly GETs, and firmware inventory.
2. **Analyze** — Parse Redfish members into AFID events; optionally decode CPER attachments; optionally call a configured hub (`analysis_args.hub_python_module`).
3. **Write logs** — Artifacts and `serviceability.json` under the run log directory (see [Output](#output)).

Connection type: **OOB Redfish** (`RedfishConnectionManager`). See [connections/overview.md](../connections/overview.md).

## Prerequisites

- **Node Scraper** installed ([README.md](../../README.md)).
- **Redfish access** to the target BMC (HTTPS, credentials).
- **AFID_SAG.json** (when running hub analysis): path on the Node Scraper host, passed to the hub at initialization.
- **Service hub** (optional): importable Python package when `skip_hub` is `false`. Install it in the same environment as `node-scraper`.
- **CPER decoder** (optional): only when events include CPER attachments that need decoding before hub analysis. Set `cper_decode_module` / `cper_decode_method` in plugin config.

## Example configs (dummy data)

Values below match the dummy URIs and fixtures used in unit tests (`test/unit/serviceability_dummy_data.py`, `test/unit/plugin/fixtures/afid_sag_sample.json`). Replace host, credentials, and paths for your environment.

### Connection config

```json
{
  "RedfishConnectionManager": {
    "host": "dummy-bmc.example",
    "port": 443,
    "username": "admin",
    "password": "secret",
    "use_https": true,
    "verify_ssl": false,
    "timeout_seconds": 30
  }
}
```

See also [connections/connection-config.md](../connections/connection-config.md).

### Plugin config — collect only (no hub)

Use `skip_hub: true` to collect Redfish data and build AFID events without calling an external hub:

```json
{
  "name": "ServiceabilityPlugin",
  "desc": "Collect dummy BMC Redfish events (no hub analysis)",
  "global_args": {},
  "plugins": {
    "ServiceabilityPluginMI3XX": {
      "collection_args": {
        "rf_event_log_uri": "/redfish/v1/Systems/Dummy/LogServices/DummyEventLog/Entries",
        "follow_next_link": true,
        "max_pages": 200
      },
      "analysis_args": {
        "skip_hub": true
      }
    }
  },
  "result_collators": {}
}
```

### Plugin config — collect and run hub

When hub analysis is enabled, set `hub_python_module`, `afid_sag_path`, and related fields. Example shape (replace module name and paths with your hub package and SAG file):

```json
{
  "name": "ServiceabilityPlugin",
  "desc": "Collect BMC Redfish events and analyze with a configured service hub",
  "global_args": {},
  "plugins": {
    "ServiceabilityPluginMI3XX": {
      "collection_args": {
        "rf_event_log_uri": "/redfish/v1/Systems/Dummy/LogServices/DummyEventLog/Entries",
        "follow_next_link": true,
        "max_pages": 200
      },
      "analysis_args": {
        "hub_python_module": "your_hub_package",
        "hub_display_name": "Example hub",
        "afid_sag_path": "test/unit/plugin/fixtures/afid_sag_sample.json",
        "hub_init_path_kwarg": "afid_sag",
        "hub_analyze_method": "get_service_info",
        "skip_hub": false,
        "cper_decode_module": "your_cper_decoder_module",
        "cper_decode_method": "analyze_cper"
      }
    }
  },
  "result_collators": {}
}
```

A copy of the collect-only example lives at [../../plugin_config_serviceability.json](../../plugin_config_serviceability.json) in the repo root.

## Run

**With plugin config file:**

```sh
node-scraper \
  --connection-config connection-config.json \
  --plugin-configs plugin_config_serviceability.json \
  --log-path ./logs \
  run-plugins ServiceabilityPluginMI3XX
```

**Inspect options:**

```sh
node-scraper describe plugin ServiceabilityPluginMI3XX
node-scraper run-plugins ServiceabilityPluginMI3XX -h
```

## Offline analysis

Skip live collection and analyze a prior data file or log directory with `--data`:

```sh
node-scraper \
  --plugin-configs plugin_config_serviceability_se.json \
  run-plugins ServiceabilityPluginMI3XX
```

Example analyze-only plugin config (`collection: false`, `analysis: true`, `data` points at a saved event log JSON):

```json
{
  "plugins": {
    "ServiceabilityPluginMI3XX": {
      "collection": false,
      "analysis": true,
      "data": "/path/to/saved_event_log.json",
      "analysis_args": {
        "skip_hub": true,
        "afid_sag_path": "test/unit/plugin/fixtures/afid_sag_sample.json"
      }
    }
  }
}
```

## Output

Logs are written under `--log-path` (default layout: `./scraper_logs_<host>_<timestamp>/`). Typical artifacts:

| Artifact | Description |
| --- | --- |
| `redfish_responses.json` | Raw collected Redfish payloads |
| `serviceability_uri_manifest.json` | URIs used for this run |
| `firmware_inventory.json` | Firmware bundle GET (when configured) |
| `serviceability.json` | AFID events and hub recommendations (after analysis) |
| `afid_sag_metadata.json` | AFID_SAG metadata from the hub (when hub runs) |
| `cper_data.json` | Decoded CPER data (when a decoder is configured) |

Per-task `events.json`, data model JSON, and collector command artifacts are also written under the plugin log subdirectory.

## Troubleshooting

- **Hub import errors** — Confirm `hub_python_module` is installed in the same Python environment as `node-scraper`.
- **Missing AFID_SAG** — `afid_sag_path` is required when `skip_hub` is `false`.
- **Empty or wrong events** — Verify `rf_event_log_uri` matches your BMC Redfish tree.
- **CPER decode failures** — Set `cper_decode_module` / `cper_decode_method`, or ensure CPER is already decoded on the log entry so attachment fetch is skipped.

## Related

- [oob.md](oob.md) — OOB plugin patterns
- [../connections/connection-config.md](../connections/connection-config.md) — Redfish connection JSON
- [../cli/configs.md](../cli/configs.md) — plugin config structure
- [../PLUGIN_DOC.md](../PLUGIN_DOC.md) — generated plugin reference
