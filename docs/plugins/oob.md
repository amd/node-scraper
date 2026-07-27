# Out-of-band (OOB) plugins

OOB plugins talk to the **BMC** — either Redfish HTTPS or SSH to the BMC shell.

## Two OOB patterns

| Base class | Connection | Use case |
| --- | --- | --- |
| `OOBandDataPlugin` | `RedfishConnectionManager` → `RedfishConnection` | Redfish GET/POST, event logs, OEM diag |
| `OOBSSHDataPlugin` | `OobSshConnectionManager` (credentials from Redfish config) | BMC shell archive, generic command collection |

Collectors use `RedfishDataCollector` (`_run_redfish_get`, `_run_redfish_get_paged`) or SSH helpers on `OOBSSHDataPlugin`.

## Redfish connection config

Required for all OOB Redfish plugins:

```json
{
  "RedfishConnectionManager": {
    "host": "bmc.example.com",
    "port": 443,
    "username": "admin",
    "password": "secret",
    "use_https": true,
    "verify_ssl": false,
    "api_root": "redfish/v1"
  }
}
```

See [../connections/connection-config.md](../connections/connection-config.md).

## Example plugins

| Plugin | Purpose |
| --- | --- |
| `RedfishEndpointPlugin` | Collect arbitrary Redfish URIs + optional JSON checks |
| `RedfishOemDiagPlugin` | OEM diagnostic log collection via LogService |
| `ServiceabilityPluginMI3XX` | MI3XX BMC event log + service hub analysis |
| `Mi4xxServiceabilityPlugin` | Mi4xx/Helios event log + hub entry point |
| `OobBmcArchivePlugin` | BMC archive via SSH |
| `OobGenericCollectionPlugin` | Generic BMC shell collection |

## RedfishEndpointPlugin

```json
{
  "plugins": {
    "RedfishEndpointPlugin": {
      "collection_args": {
        "uris": ["/redfish/v1/", "/redfish/v1/Systems/1"],
        "follow_next_link": false,
        "max_pages": 200
      },
      "analysis_args": {
        "checks": {
          "/redfish/v1/Systems/1": {
            "PowerState": "On",
            "Status/Health": { "anyOf": ["OK", "Warning"] }
          }
        }
      }
    }
  }
}
```

```sh
node-scraper --connection-config connection-config.json \
  --plugin-config plugin_config_redfish_endpoint.json \
  run-plugins RedfishEndpointPlugin
```

## Redfish OEM diagnostic plugin

1. Discover allowable types: `show-redfish-oem-allowable` (see [../cli/subcommands.md](../cli/subcommands.md)).
2. Set `oem_diagnostic_types_allowable` and `oem_diagnostic_types` in plugin config.
3. Run with Redfish connection config.

```sh
node-scraper --connection-config connection-config.json \
  --plugin-config plugin_config_redfish_oem_diag.json \
  run-plugins RedfishOemDiagPlugin
```

## Serviceability

See [../../README_SERVICEABILITY.md](../../README_SERVICEABILITY.md) for MI3XX/Mi4xx setup, hub config, and artifacts.

## Related

- [../connections/overview.md](../connections/overview.md) — Redfish sequence diagram
- [../PLUGIN_DOC.md](../PLUGIN_DOC.md) — OOB plugin catalog
- [../architecture/overview.md](../architecture/overview.md)
