# Error Scraper
Error scraper is a tool which performs automated data collection and analysis for the purposes of system debug.

## Installation
### Install From Source
Error Scraper requires Python 3.10+ for installation. After cloning this repository, call dev-setup.sh script with 'source'. This script creates an editable install of Error Scraper in a python virtual environment and also configures the pre-commit hooks for the project.

```sh
source dev-setup.sh
```

## CLI Usage
The Error Scraper CLI can be used to run Error Scraper plugins on a target system. The following CLI options are available:

```sh
usage: error-scraper [-h] [--sys-name STRING] [--sys-location {LOCAL,REMOTE}] [--sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}]
                     [--sys-sku STRING] [--sys-platform STRING] [--plugin-config STRING] [--system-config STRING]
                     [--connection-config STRING] [--log-path STRING] [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}]
                     {run-plugins} ...

Error scraper CLI

positional arguments:
  {run-plugins}         Subcommands
    run-plugins         Run a series of plugins

options:
  -h, --help            show this help message and exit
  --sys-name STRING     System name (default: MKM-L1-LANDRE53)
  --sys-location {LOCAL,REMOTE}
                        Location of target system (default: LOCAL)
  --sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}
                        Specify system interaction level, used to determine the type of actions that plugins can perform (default:
                        INTERACTIVE)
  --sys-sku STRING      Manually specify SKU of system (default: None)
  --sys-platform STRING
                        Specify system platform (default: None)
  --plugin-config STRING
                        Path to plugin config json (default: None)
  --system-config STRING
                        Path to system config json (default: None)
  --connection-config STRING
                        Path to system config json (default: None)
  --log-path STRING     Specifies local path for Scraper logs, use 'None' to disable logging (default: .)
  --log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}
                        Change python log level (default: INFO)

```

The plugins to run can be specified in two ways, using a plugin JSON config file or using the 'run-plugins' sub command. These two options are not mutually exclusive and can be used together.

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

### 'run-plugins' sub command
The plugins to run and their associated arguments can also be specified directly on the CLI using the 'run-plugins' sub-command. Using this sub-command you can specify a plugin name followed by the arguments for that particular plugin. Multiple plugins can be specified at once.

You can view the available arguments for a particular plugin by running `error-scraper run-plugins <plugin-name> -h`:
```sh
usage: error-scraper run-plugins BiosPlugin [-h] [--collection {True,False}] [--analysis {True,False}] [--system-interaction-level STRING]
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
error-scraper run-plugins BiosPlugin --exp-bios-version TestBios123
```

Run multiple plugins
```sh
error-scraper run-plugins BiosPlugin --exp-bios-version TestBios123 RocmPlugin --exp-rocm TestRocm123
```


Run plugins without specifying args (plugin defaults will be used)

```sh
error-scraper run-plugins BiosPlugin RocmPlugin
```

Use plugin configs and 'run-plugins'

```sh
error-scraper run-plugins BiosPlugin
```
