# Node Scraper
Node Scraper is a tool which performs automated data collection and analysis for the purposes of system debug.

## Installation
### Install From Source
Node Scraper requires Python 3.10+ for installation. After cloning this repository, call dev-setup.sh script with 'source'. This script creates an editable install of Node Scraper in a python virtual environment and also configures the pre-commit hooks for the project.

```sh
source dev-setup.sh
```

## CLI Usage
The Node Scraper CLI can be used to run Node Scraper plugins on a target system. The following CLI options are available:

```sh
usage: node-scraper [-h] [--sys-name STRING] [--sys-location {LOCAL,REMOTE}] [--sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}]
                     [--sys-sku STRING] [--sys-platform STRING] [--plugin-config STRING] [--system-config STRING] [--connection-config STRING]
                     [--log-path STRING] [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}]
                     {run-plugins,gen-plugin-config,describe} ...

Error scraper CLI

positional arguments:
  {run-plugins,gen-plugin-config,describe}
                        Subcommands
    run-plugins         Run a series of plugins
    gen-plugin-config   Generate a config for a plugin or list of plugins
    describe            Display details on a built-in config or plugin

options:
  -h, --help            show this help message and exit
  --sys-name STRING     System name (default: MKM-L1-LANDRE53)
  --sys-location {LOCAL,REMOTE}
                        Location of target system (default: LOCAL)
  --sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}
                        Specify system interaction level, used to determine the type of actions that plugins can perform (default: INTERACTIVE)
  --sys-sku STRING      Manually specify SKU of system (default: None)
  --sys-platform STRING
                        Specify system platform (default: None)
  --plugin-config STRING
                        Path to plugin config json (default: None)
  --system-config STRING
                        Path to system config json (default: None)
  --connection-config STRING
                        Path to connection config json (default: None)
  --log-path STRING     Specifies local path for node scraper logs, use 'None' to disable logging (default: .)
  --log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}
                        Change python log level (default: INFO)

```

The plugins to run can be specified in two ways, using a plugin JSON config file or using the 'run-plugins' sub command. These two options are not mutually exclusive and can be used together.

---

### Describing Built-in Configs and Plugins

You can use the `describe` subcommand to display details about built-in configs or plugins.

#### List all built-in configs:
```sh
node-scraper describe config
```

#### Show details for a specific built-in config:
```sh
node-scraper describe config <config-name>
```

#### List all available plugins:
```sh
node-scraper describe plugin
```

#### Show details for a specific plugin:
```sh
node-scraper describe plugin <plugin-name>
```

---

### Plugin Configs
A plugin JSON config should follow the structure of the plugin config model defined here. The globals field is a dictionary of global key-value pairs; values in globals will be passed to any plugin that supports the corresponding key. The plugins field should be a dictionary mapping plugin names to sub-dictionaries of plugin arguments. Lastly, the result_collators attribute is used to define result collator classes that will be run on the plugin results. By default, the CLI adds the TableSummary result collator, which prints a summary of each plugin’s results in a tabular format to the console.

```json
{
    "globals_args": {},
    "plugins": {
        "BiosPlugin": {
            "analysis_args": {
                "exp_bios_version": "TestBios123"
            }
        },
        "RocmPlugin": {
            "analysis_args": {
                "exp_rocm_version": "TestRocm123"
            }
        }
    }
}
```

### 'gen-plugin-config' sub command
The 'gen-plugin-config' sub command can be used to generate a plugin config JSON file for a plugin or list of plugins that can then be customized. Plugin arguments which have default values will be prepopulated in the JSON file, arguments without default values will have a value of 'null'.

#### 'gen-plugin-config' Examples

Generate a config for the DmesgPlugin:
```sh
node-scraper gen-plugin-config DmesgPlugin
```

This would produce the following config:

```json
{
  "global_args": {},
  "plugins": {
    "DmesgPlugin": {
      "collection": true,
      "analysis": true,
      "system_interaction_level": "INTERACTIVE",
      "data": null,
      "analysis_args": {
        "analysis_range_start": null,
        "analysis_range_end": null,
        "check_unknown_dmesg_errors": true,
        "exclude_category": null
      }
    }
  },
  "result_collators": {}
}
```

### 'run-plugins' sub command
The plugins to run and their associated arguments can also be specified directly on the CLI using the 'run-plugins' sub-command. Using this sub-command you can specify a plugin name followed by the arguments for that particular plugin. Multiple plugins can be specified at once.

You can view the available arguments for a particular plugin by running `node-scraper run-plugins <plugin-name> -h`:
```sh
usage: node-scraper run-plugins BiosPlugin [-h] [--collection {True,False}] [--analysis {True,False}] [--system-interaction-level STRING]
                                            [--data STRING] [--exp-bios-version [STRING ...]] [--regex-match {True,False}]

options:
  -h, --help            show this help message and exit
  --collection {True,False}
  --analysis {True,False}
  --system-interaction-level STRING
  --data STRING
  --exp-bios-version [STRING ...]
  --regex-match {True,False}

```

#### 'run-plugins' Examples

Run a single plugin
```sh
node-scraper run-plugins BiosPlugin --exp-bios-version TestBios123
```

Run multiple plugins
```sh
node-scraper run-plugins BiosPlugin --exp-bios-version TestBios123 RocmPlugin --exp-rocm TestRocm123
```

Run plugins without specifying args (plugin defaults will be used)

```sh
node-scraper run-plugins BiosPlugin RocmPlugin
```

Use plugin configs and 'run-plugins'

```sh
node-scraper run-plugins BiosPlugin
```
