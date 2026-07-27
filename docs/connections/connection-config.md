# Connection config

Use `--connection-config` to pass a JSON file with one or more connection manager blocks. Keys must match registered manager names.

## In-band (SSH)

Remote host OS access:

```json
{
  "InBandConnectionManager": {
    "hostname": "remote_host.example.com",
    "port": 22,
    "username": "myuser",
    "password": "mypassword",
    "key_filename": "/path/to/private/key"
  }
}
```

Run with:

```sh
node-scraper --sys-name remote_host --sys-location REMOTE \
  --connection-config connection_config.json \
  run-plugins DmesgPlugin
```

Notes:

- Use `key_filename` instead of `password` for key-based auth.
- Remote user needs permissions for plugin commands; use `--skip-sudo` to skip plugins that require sudo.

## Out-of-band (Redfish)

BMC Redfish HTTPS access for OOB plugins:

```json
{
  "RedfishConnectionManager": {
    "host": "bmc.example.com",
    "port": 443,
    "username": "admin",
    "password": "secret",
    "use_https": true,
    "verify_ssl": true,
    "api_root": "redfish/v1"
  }
}
```

Run with:

```sh
node-scraper --connection-config connection-config.json \
  --plugin-config plugin_config_redfish_endpoint.json \
  run-plugins RedfishEndpointPlugin
```

- **`api_root`** (optional) — Redfish API path; defaults to `redfish/v1`.
- **`verify_ssl`** — set `false` for lab BMCs with self-signed certs.

## Combined config

You can include both managers when a run uses in-band and OOB plugins (unusual for a single queue; more common when switching configs between runs):

```json
{
  "InBandConnectionManager": { "hostname": "host.example.com", "username": "user", "password": "..." },
  "RedfishConnectionManager": { "host": "bmc.example.com", "username": "admin", "password": "..." }
}
```

## OOB SSH plugins

`OOBSSHDataPlugin` (e.g. `OobBmcArchivePlugin`) uses **`RedfishConnectionManager`** credentials in the JSON file. `PluginExecutor` routes those credentials to `OobSshConnectionManager` (SSH port 22 to the BMC host).

## Related

- [overview.md](overview.md) — in-band vs OOB patterns
- [../cli/subcommands.md](../cli/subcommands.md) — `show-redfish-oem-allowable`
