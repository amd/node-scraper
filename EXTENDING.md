# Extending Node Scraper

This guide covers how to integrate Nodescraper into another Python tool and how to create and use external plugins.

## Table of Contents
- [nodescraper integration](#nodescraper-integration)
- [programmatic usage improvements](#programmatic-usage-improvements)
- [external plugins](#external-plugins)

## nodescraper integration
Nodescraper can be integrated inside another Python tool by leveraging its classes and functionality.
See below for a comprehensive example on how to create plugins and run the associated data
collection and analysis.
Sample run command:
```sh
python3 sample.py
```

Sample.py file:
```python
import logging
import sys
from nodescraper.plugins.inband.bios.bios_plugin import BiosPlugin
from nodescraper.plugins.inband.bios.analyzer_args import BiosAnalyzerArgs
from nodescraper.plugins.inband.kernel.kernel_plugin import KernelPlugin
from nodescraper.plugins.inband.kernel.analyzer_args import KernelAnalyzerArgs
from nodescraper.plugins.inband.os.os_plugin import OsPlugin
from nodescraper.plugins.inband.os.analyzer_args import OsAnalyzerArgs
from nodescraper.models.systeminfo import SystemInfo, OSFamily
from nodescraper.enums import EventPriority, SystemLocation
from nodescraper.resultcollators.tablesummary import TableSummary
from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.inband.sshparams import SSHConnectionParams
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.models.pluginconfig import PluginConfig
from nodescraper.pluginexecutor import PluginExecutor

def main():

    #setting up my custom logger
    log_level = "INFO"
    handlers = [logging.StreamHandler(stream=sys.stdout)]
    logging.basicConfig(
        force=True,
        level=log_level,
        format="%(asctime)25s %(levelname)10s %(name)25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %Z",
        handlers=handlers,
        encoding="utf-8",
    )
    logging.root.setLevel(logging.INFO)
    logging.getLogger("paramiko").setLevel(logging.ERROR)
    logger = logging.getLogger("nodescraper")

    #setting up system info
    system_info = SystemInfo(name="test_host",
                            platform="X",
                            os_familty=OSFamily.LINUX,
                            sku="some_sku")

    #initiate plugins
    bios_plugin = BiosPlugin(system_info=system_info, logger=logger)
    kernel_plugin = KernelPlugin(system_info=system_info, logger=logger)

    #launch data collection
    _ = bios_plugin.collect()
    _ = kernel_plugin.collect()

    #launch data analysis
    bios_plugin.analyze(analysis_args=BiosAnalyzerArgs(exp_bios_version="XYZ"))
    kernel_plugin.analyze(analysis_args=KernelAnalyzerArgs(exp_kernel="ABC"))

    #log plugin data models
    logger.info(kernel_plugin.data.model_dump())
    logger.info(bios_plugin.data.model_dump())

    #alternate method
    all_res = []

    #launch plugin collection & analysis
    bios_result = bios_plugin.run(analysis_args={"exp_bios_version":"ABC"})
    all_res.append(bios_result)
    table_summary = TableSummary()
    table_summary.collate_results(all_res, None)

    #remote connection
    system_info.location=SystemLocation.REMOTE
    ssh_params = SSHConnectionParams(hostname="my_system",
                                    port=22,
                                    username="my_username",
                                    key_filename="/home/user/.ssh/ssh_key")
    conn_manager = InBandConnectionManager(system_info=system_info, connection_args=ssh_params)
    os_plugin = OsPlugin(system_info=system_info, logger=logger, connection_manager=conn_manager)
    os_plugin.run(analysis_args=OsAnalyzerArgs(exp_os="DEF"))

    #run multiple plugins through a queue
    system_info.location=SystemLocation.LOCAL
    config_dict = {
      "global_args": {
          "collection" : 1,
          "analysis" : 1
      },
      "plugins": {
        "BiosPlugin": {
          "analysis_args": {
            "exp_bios_version": "123",
          }
        },
        "KernelPlugin": {
          "analysis_args": {
            "exp_kernel": "ABC",
          }
        }
      },
      "result_collators": {},
      "name": "plugin_config",
      "desc": "Auto generated config"
      }

    config1 = PluginConfig(**config_dict)
    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=[config1],
        system_info=system_info
    )
    results = plugin_executor.run_queue()



if __name__ == "__main__":
    main()
```

## programmatic usage improvements

Node-scraper provides built-in features to simplify programmatic integration:

### Quiet Mode

Suppress console logging output while maintaining file logging:

```python
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.models.pluginconfig import PluginConfig

config = PluginConfig(
    name="my_config",
    plugins={"DmesgPlugin": {}}
)

# Suppress console output
executor = PluginExecutor(
    plugin_configs=[config],
    log_path="/tmp/logs",
    quiet=True  # No console output, but files are still written
)

results = executor.run_queue()
```

### PluginResult Helper Methods

Access common data using simplified helper methods:

```python
# Run plugins
executor = PluginExecutor(
    plugin_configs=[config],
    log_path="/tmp/logs",
    quiet=True
)
results = executor.run_queue()

for result in results:
    # Get collected system data
    system_data = result.get_system_data()
    if system_data:
        print(f"Collected data from {result.source}")

    # Get analysis events
    events = result.get_analysis_events()
    for event in events:
        print(f"{event.priority}: {event.description}")

    # Get all artifact file paths
    files = result.get_artifact_files()
    for file_path in files:
        print(f"Created: {file_path}")
```

### Artifact File Path Tracking

All files written by plugins are automatically tracked:

```python
results = executor.run_queue()

for result in results:
    # Access all files created by the plugin
    artifact_files = result.get_artifact_files()

    # Files include:
    # - result.json
    # - events.json (if events exist)
    # - data model files (e.g., dmesg.log)
    # - artifact files (e.g., command outputs)

    for file_path in artifact_files:
        assert os.path.exists(file_path)
```

### Complete Example

```python
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.models.pluginconfig import PluginConfig
from nodescraper.models.systeminfo import SystemInfo
from nodescraper.enums import SystemLocation

# Simple configuration
plugin_config = PluginConfig(
    name="passive_collection",
    plugins={
        "DmesgPlugin": {
            "analysis_args": {
                "analysis_range_start": "2024-01-01T00:00:00",
                "analysis_range_end": "2024-01-02T00:00:00"
            },
            "collection_args": {
                "log_dmesg_data": False  # Don't write large log files
            }
        }
    }
)

# Create executor with quiet mode
executor = PluginExecutor(
    plugin_configs=[plugin_config],
    system_info=SystemInfo(name="my_host", location=SystemLocation.LOCAL),
    log_path="/tmp/nodescraper_logs",
    quiet=True  # Suppress console output
)

# Execute plugins
try:
    results = executor.run_queue()

    for result in results:
        print(f"Plugin: {result.source}")
        print(f"Status: {result.status}")

        # Use helper methods for easy data access
        system_data = result.get_system_data()
        events = result.get_analysis_events()
        files = result.get_artifact_files()

        print(f"Events found: {len(events)}")
        print(f"Files created: {len(files)}")

        # Process events
        errors = [e for e in events if e.priority.value >= 3]
        if errors:
            print(f"Found {len(errors)} errors!")

except Exception as e:
    print(f"Execution failed: {e}")
```

## external plugins
External plugins can be added and installed in the same env as node-scraper plugins. See -> [docs/node-scraper-external/README.md](docs/node-scraper-external/README.md)
