# Node Scraper
Node Scraper is a tool which performs automated data collection and analysis for the purposes of
system debug.

## Table of Contents
- [Installation](#installation)
  - [Install From Source](#install-from-source)
- [CLI Usage](#cli-usage)
  - [Execution Methods](#execution-methods)
    - [Example: Remote Execution](#example-remote-execution)
    - [Example: connection_config.json](#example-connection_configjson)
  - [Subcommands](#subcommands)
    - ['describe' subcommand](#describe-subcommand)
    - ['run-plugins' sub command](#run-plugins-sub-command)
    - ['gen-plugin-config' sub command](#gen-plugin-config-sub-command)
    - ['summary' sub command](#summary-sub-command)
- [Configs](#configs)
  - [Global args](#global-args)
  - [Plugin config: `--plugin-configs` command](#plugin-config---plugin-configs-command)
  - [Reference config: `gen-reference-config` command](#reference-config-gen-reference-config-command)
- **Extending Node Scraper (integration & external plugins)** → See [EXTENDING.md](EXTENDING.md)
- **Full view of the plugins with the associated collectors & analyzers as well as the commands
invoked by collectors** -> See [docs/PLUGIN_DOC.md](docs/PLUGIN_DOC.md)

## Installation
### Install From Source
Node Scraper requires Python 3.9+ for installation. After cloning this repository,
call dev-setup.sh script with 'source'. This script creates an editable install of Node Scraper in
a python virtual environment and also configures the pre-commit hooks for the project.

```sh
source dev-setup.sh
```

Alternatively, follow these manual steps:

### 1. Virtual Environment (Optional)
```sh
python3 -m venv venv
source venv/bin/activate
```
On Debian/Ubuntu, you may need: `sudo apt install python3-venv`

### 2. Install from Source (Required)
```sh
python3 -m pip install --editable .[dev] --upgrade
```
This installs Node Scraper in editable mode with development dependencies. To verify: `node-scraper --help`

### 3. Git Hooks (Optional)
```sh
pre-commit install
```
Sets up pre-commit hooks for code quality checks. On Debian/Ubuntu, you may need: `sudo apt install pre-commit`

## CLI Usage
The Node Scraper CLI can be used to run Node Scraper plugins on a target system. The following CLI
options are available:

```sh
usage: node-scraper [-h] [--sys-name STRING] [--sys-location {LOCAL,REMOTE}] [--sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}] [--sys-sku STRING]
                    [--sys-platform STRING] [--plugin-configs [STRING ...]] [--system-config STRING] [--connection-config STRING] [--log-path STRING]
                    [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}] [--gen-reference-config] [--skip-sudo]
                    {summary,run-plugins,describe,gen-plugin-config} ...

node scraper CLI

positional arguments:
  {summary,run-plugins,describe,gen-plugin-config}
                        Subcommands
    summary             Generates summary csv file
    run-plugins         Run a series of plugins
    describe            Display details on a built-in config or plugin
    gen-plugin-config   Generate a config for a plugin or list of plugins

options:
  -h, --help            show this help message and exit
  --sys-name STRING     System name (default: <my_system_name>)
  --sys-location {LOCAL,REMOTE}
                        Location of target system (default: LOCAL)
  --sys-interaction-level {PASSIVE,INTERACTIVE,DISRUPTIVE}
                        Specify system interaction level, used to determine the type of actions that plugins can perform (default: INTERACTIVE)
  --sys-sku STRING      Manually specify SKU of system (default: None)
  --sys-platform STRING
                        Specify system platform (default: None)
  --plugin-configs [STRING ...]
                        built-in config names or paths to plugin config JSONs. Available built-in configs: NodeStatus (default: None)
  --system-config STRING
                        Path to system config json (default: None)
  --connection-config STRING
                        Path to connection config json (default: None)
  --log-path STRING     Specifies local path for node scraper logs, use 'None' to disable logging (default: .)
  --log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}
                        Change python log level (default: INFO)
  --gen-reference-config
                        Generate reference config from system. Writes to ./reference_config.json. (default: False)
  --skip-sudo           Skip plugins that require sudo permissions (default: False)

```

### Execution Methods

Node Scraper can operate in two modes: LOCAL and REMOTE, determined by the `--sys-location` argument.

- **LOCAL** (default): Node Scraper is installed and run directly on the target system. All data collection and plugin execution occur locally.
- **REMOTE**: Node Scraper runs on your local machine but targets a remote system over SSH. In this mode, Node Scraper does not need to be installed on the remote system; all commands are executed remotely via SSH.

To use remote execution, specify `--sys-location REMOTE` and provide a connection configuration file with `--connection-config`.

#### Example: Remote Execution

```sh
node-scraper --sys-name <remote_host> --sys-location REMOTE --connection-config ./connection_config.json run-plugins DmesgPlugin
```

##### Example: connection_config.json

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

**Notes:**
- If using SSH keys, specify `key_filename` instead of `password`.
- The remote user must have permissions to run the requested plugins and access required files. If needed, use the `--skip-sudo` argument to skip plugins requiring sudo.

### Subcommands

Plugins to run can be specified in two ways, using a plugin JSON config file or using the
'run-plugins' sub command. These two options are not mutually exclusive and can be used together.

#### **'describe' subcommand**

You can use the `describe` subcommand to display details about built-in configs or plugins.
List all built-in configs:
```sh
node-scraper describe config
```

Show details for a specific built-in config
```sh
node-scraper describe config <config-name>
```

List all available plugins**
```sh
node-scraper describe plugin
```

Show details for a specific plugin
```sh
node-scraper describe plugin <plugin-name>
```

#### **'run-plugins' sub command**
The plugins to run and their associated arguments can also be specified directly on the CLI using
the 'run-plugins' sub-command. Using this sub-command you can specify a plugin name followed by
the arguments for that particular plugin. Multiple plugins can be specified at once.

You can view the available arguments for a particular plugin by running
`node-scraper run-plugins <plugin-name> -h`:
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

Examples

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

#### **'gen-plugin-config' sub command**
The 'gen-plugin-config' sub command can be used to generate a plugin config JSON file for a plugin
or list of plugins that can then be customized. Plugin arguments which have default values will be
prepopulated in the JSON file, arguments without default values will have a value of 'null'.

Examples

Generate a config for the DmesgPlugin:
```sh
node-scraper gen-plugin-config --plugins DmesgPlugin
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

#### **'summary' sub command**
The 'summary' subcommand can be used to combine results from multiple runs of node-scraper to a
single summary.csv file. Sample run:
```sh
node-scraper summary --summary_path /<path_to_node-scraper_logs>
```
This will generate a new file '/<path_to_node-scraper_logs>/summary.csv' file. This file will
contain the results from all 'nodescraper.csv' files from '/<path_to_node-scarper_logs>'.

### Configs
A plugin JSON config should follow the structure of the plugin config model defined here.
The globals field is a dictionary of global key-value pairs; values in globals will be passed to
any plugin that supports the corresponding key. The plugins field should be a dictionary mapping
plugin names to sub-dictionaries of plugin arguments. Lastly, the result_collators attribute is
used to define result collator classes that will be run on the plugin results. By default, the CLI
adds the TableSummary result collator, which prints a summary of each plugin’s results in a
tabular format to the console.

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

#### Global args
Global args can be used to skip sudo plugins or enable/disble either collection or analysis.
Below is an example that skips sudo requiring plugins and disables analysis.

```json
  "global_args": {
      "collection_args": {
        "skip_sudo" : 1
      },
      "collection" : 1,
      "analysis" : 0
  },
```

#### Plugin config: **'--plugin-configs' command**
A plugin config can be used to compare the system data against the config specifications:
```sh
node-scraper --plugin-configs plugin_config.json
```
Here is an example of a comprehensive plugin config that specifies analyzer args for each plugin:
```json
{
  "global_args": {},
  "plugins": {
    "BiosPlugin": {
      "analysis_args": {
        "exp_bios_version": "3.5"
      }
    },
    "CmdlinePlugin": {
      "analysis_args": {
        "cmdline": "imgurl=test NODE=nodename selinux=0 serial console=ttyS1,115200 console=tty0",
        "required_cmdline" : "selinux=0"
      }
    },
    "DkmsPlugin": {
      "analysis_args": {
        "dkms_status": "amdgpu/6.11",
        "dkms_version" : "dkms-3.1",
        "regex_match" : true
      }
    },
    "KernelPlugin": {
      "analysis_args": {
        "exp_kernel": "5.11-generic"
      }
    },
    "OsPlugin": {
      "analysis_args": {
        "exp_os": "Ubuntu 22.04.2 LTS"
      }
    },
    "PackagePlugin": {
          "analysis_args": {
            "exp_package_ver": {
              "gcc": "11.4.0"
            },
            "regex_match": false
          }
    },
    "RocmPlugin": {
      "analysis_args": {
        "exp_rocm": "6.5"
      }
    }
  },
  "result_collators": {},
  "name": "plugin_config",
  "desc": "My golden config"
}
```

#### Reference config: **'gen-reference-config' command**
This command can be used to generate a reference config that is populated with current system
configurations. Plugins that use analyzer args (where applicable) will be populated with system
data.
Sample command:
```sh
node-scraper --gen-reference-config run-plugins BiosPlugin OsPlugin

```
This will generate the following config:
```json
{
  "global_args": {},
  "plugins": {
    "BiosPlugin": {
      "analysis_args": {
        "exp_bios_version": [
          "M17"
        ],
        "regex_match": false
      }
    },
    "OsPlugin": {
      "analysis_args": {
        "exp_os": [
          "8.10"
        ],
        "exact_match": true
      }
    }
  },
  "result_collators": {}
```
This config can later be used on a different platform for comparison, using the steps at #2:
```sh
node-scraper --plugin-configs reference_config.json

```

An alternate way to generate a reference config is by using log files from a previous run. The
example below uses log files from 'scraper_logs_<path>/':
```sh
node-scraper gen-plugin-config --gen-reference-config-from-logs scraper_logs_<path>/ --output-path custom_output_dir
```
This will generate a reference config that includes plugins with logged results in
'scraper_log_<path>' and save the new config to 'custom_output_dir/reference_config.json'.
