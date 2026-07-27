# Architecture overview

Node Scraper collects and analyzes system data through **plugins**. Each plugin runs a **collector** (gather raw data) and optionally an **analyzer** (check data and emit events). The CLI loads configs, builds a plugin queue, connects to the target system, runs plugins, and writes logs.

## High-level flow

```mermaid
flowchart TB
    subgraph CLI["CLI (node-scraper)"]
        A[Parse args + subcommand]
        B[Load plugin configs]
        C[PluginRegistry]
    end

    subgraph Exec["PluginExecutor"]
        D[Plugin queue]
        E[Connection library]
        F[Run each plugin.run]
        G[Result collators]
    end

    subgraph Plugin["DataPlugin"]
        H[collect → DataCollector]
        I[analyze → DataAnalyzer]
    end

    subgraph Conn["Connection managers"]
        J[InBandConnectionManager]
        K[RedfishConnectionManager]
        L[OobSshConnectionManager]
    end

    subgraph Target["Target system"]
        M[Local shell / SSH host]
        N[BMC Redfish REST]
        O[BMC SSH shell]
    end

    subgraph Output["Run output"]
        P[events.json per task]
        Q[Data model artifacts]
        R[nodescraper.csv + TableSummary]
    end

    A --> B --> C --> D
    D --> E
    E --> J
    E --> K
    E --> L
    D --> F
    F --> H
    F --> I
    H --> J
    H --> K
    H --> L
    J --> M
    K --> N
    L --> O
    H --> P
    I --> P
    H --> Q
    I --> Q
    F --> G --> R
```

## Step-by-step

1. **CLI entry** — `node-scraper` invokes `nodescraper/cli/cli.py::main()`. Global flags set system info, log path, and optional `--connection-config` / `--plugin-configs`.

2. **Plugin discovery** — `PluginRegistry` loads built-in plugins from `nodescraper/plugins/` and external plugins from `[project.entry-points."nodescraper.plugins"]`.

3. **Queue** — `run-plugins` (default subcommand) builds a queue from CLI plugin names and/or JSON plugin configs. `PluginExecutor.run_queue()` runs plugins in order.

4. **Connections** — Each plugin declares a `CONNECTION_TYPE`. The executor resolves a connection manager from `--connection-config` or creates one lazily:
   - **In-band** — `InBandConnectionManager` → local shell or SSH to the host OS.
   - **OOB Redfish** — `RedfishConnectionManager` → HTTPS REST to the BMC (`RedfishConnection.run_get`, paging helpers).
   - **OOB SSH** — `OobSshConnectionManager` (uses Redfish config credentials, SSH to BMC) for BMC-shell plugins.

5. **Collect / analyze** — `DataPlugin.run()` calls `COLLECTOR.collect_data()` then `ANALYZER.analyze_data()`. Collectors receive the live connection object; analyzers work on the in-memory data model.

6. **Events and logs** — Tasks build `Event` objects on failures or rule matches. `FileSystemLogHook` writes `events.json` and data model files under `scraper_logs_<host>_<timestamp>/`. Result collators (default: `TableSummary`) print a summary table.

## In-band vs out-of-band (at a glance)

| Path | Plugin base | Connection | Typical data source |
| --- | --- | --- | --- |
| In-band | `InBandDataPlugin` | `InBandConnectionManager` | dmesg, ROCm, PCIe, packages on the host OS |
| OOB Redfish | `OOBandDataPlugin` | `RedfishConnectionManager` | Redfish GETs, OEM diag, serviceability event logs |
| OOB BMC SSH | `OOBSSHDataPlugin` | `OobSshConnectionManager` | Shell commands on the BMC |

See [connections/overview.md](../connections/overview.md) for connection JSON and Redfish reachability details.

## Key source files

| Area | Path |
| --- | --- |
| CLI | `nodescraper/cli/cli.py`, `nodescraper/cli/invocation.py` |
| Executor | `nodescraper/pluginexecutor.py` |
| Plugin contract | `nodescraper/interfaces/dataplugin.py` |
| In-band base | `nodescraper/base/inbandcollectortask.py` |
| Redfish collector base | `nodescraper/base/redfishcollectortask.py` |
| Redfish HTTP | `nodescraper/connection/redfish/redfish_connection.py` |
| Events | `nodescraper/interfaces/task.py`, `nodescraper/models/event.py` |
| Log hook | `nodescraper/taskresulthooks/filesystemloghook.py` |

## How OOB plugins reach Redfish

```mermaid
sequenceDiagram
    participant User
    participant CLI as node-scraper CLI
    participant PE as PluginExecutor
    participant RCM as RedfishConnectionManager
    participant RC as RedfishConnection
    participant BMC as BMC Redfish API
    participant Col as RedfishDataCollector

    User->>CLI: --connection-config redfish.json
    User->>CLI: run-plugins RedfishEndpointPlugin
    CLI->>PE: run_queue()
    PE->>RCM: connect(host, credentials)
    RCM->>RC: create session
    RC->>BMC: GET /redfish/v1/
    BMC-->>RC: service root
    PE->>Col: collect_data(connection=RC)
    Col->>RC: run_get("/redfish/v1/Systems/1")
    RC->>BMC: HTTPS GET
    BMC-->>RC: JSON response
    Col-->>PE: DataModel + events
```

Redfish-only subcommands (for example `show-redfish-oem-allowable`) instantiate `RedfishConnection` directly in the CLI without running a full plugin.

## Related docs

- [events-and-results.md](events-and-results.md) — event creation and log layout
- [../cli/subcommands.md](../cli/subcommands.md) — CLI reference
- [../PLUGIN_DOC.md](../PLUGIN_DOC.md) — per-plugin catalog
