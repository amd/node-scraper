###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import argparse
import datetime
import json
import logging
import os
import platform
import sys
from typing import Optional

from nodescraper.cli.constants import DEFAULT_CONFIG, META_VAR_MAP
from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.cli.inputargtypes import ModelArgHandler, json_arg, log_path_arg
from nodescraper.configbuilder import ConfigBuilder
from nodescraper.configregistry import ConfigRegistry
from nodescraper.constants import DEFAULT_LOGGER
from nodescraper.enums import ExecutionStatus, SystemInteractionLevel, SystemLocation
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.resultcollators.tablesummary import TableSummary


def build_parser(
    plugin_reg: PluginRegistry,
    config_reg: ConfigRegistry,
) -> tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]:
    """Build an argument parser

    Args:
        plugin_reg (PluginRegistry): registry of plugins

    Returns:
        tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]: tuple containing main
        parser and subparsers for each plugin module
    """
    parser = argparse.ArgumentParser(
        description="node scraper CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--sys-name", default=platform.node(), help="System name", metavar=META_VAR_MAP[str]
    )

    parser.add_argument(
        "--sys-location",
        type=str.upper,
        choices=[e.name for e in SystemLocation],
        default="LOCAL",
        help="Location of target system",
    )

    parser.add_argument(
        "--sys-interaction-level",
        type=str.upper,
        choices=[e.name for e in SystemInteractionLevel],
        default="INTERACTIVE",
        help="Specify system interaction level, used to determine the type of actions that plugins can perform",
    )

    parser.add_argument(
        "--sys-sku",
        type=str.upper,
        required=False,
        help="Manually specify SKU of system",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--sys-platform",
        type=str,
        required=False,
        help="Specify system platform",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--plugin-configs",
        type=str,
        nargs="*",
        help=f"built-in config names or paths to plugin config JSONs.\nAvailable built-in configs: {', '.join(config_reg.configs.keys())}",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-config",
        type=ModelArgHandler(SystemInfo).process_file_arg,
        required=False,
        help="Path to system config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--connection-config",
        type=json_arg,
        required=False,
        help="Path to connection config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-path",
        default=".",
        type=log_path_arg,
        help="Specifies local path for node scraper logs, use 'None' to disable logging",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=logging._nameToLevel,
        help="Change python log level",
    )

    subparsers = parser.add_subparsers(dest="subcmd", help="Subcommands")

    run_plugin_parser = subparsers.add_parser(
        "run-plugins",
        help="Run a series of plugins",
    )

    describe_parser = subparsers.add_parser(
        "describe",
        help="Display details on a built-in config or plugin",
    )

    describe_parser.add_argument(
        "type",
        choices=["config", "plugin"],
        help="Type of object to describe (config or plugin)",
    )

    describe_parser.add_argument(
        "name",
        nargs="?",
        help="Name of the config or plugin to describe",
    )

    config_builder_parser = subparsers.add_parser(
        "gen-plugin-config",
        help="Generate a config for a plugin or list of plugins",
    )

    config_builder_parser.add_argument(
        "--plugins",
        nargs="*",
        choices=list(plugin_reg.plugins.keys()),
        help="Plugins to generate config for",
    )

    config_builder_parser.add_argument(
        "--built-in-configs",
        nargs="*",
        choices=list(config_reg.configs.keys()),
        help="Built in config names",
    )

    config_builder_parser.add_argument(
        "--output-path",
        default=os.getcwd(),
        help="Directory to store config",
    )

    config_builder_parser.add_argument(
        "--config-name",
        default="plugin_config.json",
        help="Name of config file",
    )

    plugin_subparsers = run_plugin_parser.add_subparsers(
        dest="plugin_name", help="Available plugins"
    )

    plugin_subparser_map = {}
    for plugin_name, plugin_class in plugin_reg.plugins.items():
        plugin_subparser = plugin_subparsers.add_parser(
            plugin_name,
            help=f"Run {plugin_name} plugin",
        )
        try:
            parser_builder = DynamicParserBuilder(plugin_subparser, plugin_class)
            model_type_map = parser_builder.build_plugin_parser()
        except Exception as e:
            print(f"Exception building arg parsers for {plugin_name}: {str(e)}")  # noqa: T201
        plugin_subparser_map[plugin_name] = (plugin_subparser, model_type_map)

    return parser, plugin_subparser_map


def setup_logger(log_level: str = "INFO", log_path: str | None = None) -> logging.Logger:
    """set up root logger when using the CLI

    Args:
        log_level (str): log level to use
        log_path (str | None): optional path to filesystem log location

    Returns:
        logging.Logger: logger intstance
    """
    log_level = getattr(logging, log_level, "INFO")

    handlers = [logging.StreamHandler(stream=sys.stdout)]

    if log_path:
        log_file_name = os.path.join(log_path, "errorscraper.log")
        handlers.append(
            logging.FileHandler(filename=log_file_name, mode="wt", encoding="utf-8"),
        )

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

    logger = logging.getLogger(DEFAULT_LOGGER)

    return logger


def get_system_info(args: argparse.Namespace) -> SystemInfo:
    """build system info object using args

    Args:
        args (argparse.Namespace): parsed args

    Raises:
        argparse.ArgumentTypeError: if system location arg is invalid

    Returns:
        SystemInfo: system info instance
    """

    if args.system_config:
        system_info = args.system_config
    else:
        system_info = SystemInfo()

    if args.sys_name:
        system_info.name = args.sys_name

    if args.sys_sku:
        system_info.sku = args.sys_sku

    if args.sys_platform:
        system_info.platform = args.sys_platform

    if args.sys_location:
        try:
            location = getattr(SystemLocation, args.sys_location)
        except Exception as e:
            raise argparse.ArgumentTypeError("Invalid input for system location") from e

        system_info.location = location

    return system_info


def get_plugin_configs(
    plugin_config_input: list[str],
    system_interaction_level: SystemInteractionLevel,
    built_in_configs: dict[str, PluginConfig],
    parsed_plugin_args: dict[str, argparse.Namespace],
    plugin_subparser_map: dict[str, tuple[argparse.ArgumentParser, dict]],
) -> list[PluginConfig]:
    """Build list of plugin configs based on input args

    Args:
        plugin_config_input (list[str]): list of plugin config inputs, can be paths to JSON files or built-in config names
        system_interaction_level (SystemInteractionLevel): system interaction level, used to determine the type of actions that plugins can perform
        built_in_configs (dict[str, PluginConfig]): built-in plugin configs, mapping from config name to PluginConfig instance
        parsed_plugin_args (dict[str, argparse.Namespace]): parsed plugin arguments, mapping from plugin name to parsed args
        plugin_subparser_map (dict[str, tuple[argparse.ArgumentParser, dict]]): plugin subparser map, mapping from plugin name to tuple of parser and model type map

    Raises:
        argparse.ArgumentTypeError: if system interaction level is invalid
        argparse.ArgumentTypeError: if no plugin config found for a given input

    Returns:
        list[PluginConfig]: list of PluginConfig instances based on input args
    """
    try:
        system_interaction_level = getattr(SystemInteractionLevel, system_interaction_level)
    except Exception as e:
        raise argparse.ArgumentTypeError("Invalid input for system interaction level") from e

    base_config = PluginConfig(result_collators={str(TableSummary.__name__): {}})

    base_config.global_args["system_interaction_level"] = system_interaction_level

    plugin_configs = [base_config]

    if plugin_config_input:
        for config in plugin_config_input:
            if os.path.exists(config):
                plugin_configs.append(ModelArgHandler(PluginConfig).process_file_arg(config))
            elif config in built_in_configs:
                plugin_configs.append(built_in_configs[config])
            else:
                raise argparse.ArgumentTypeError(f"No plugin config found for: {config}")

    if parsed_plugin_args:
        plugin_input_config = PluginConfig()

        for plugin, plugin_args in parsed_plugin_args.items():
            config = {}
            model_type_map = plugin_subparser_map[plugin][1]
            for arg, val in vars(plugin_args).items():
                if val is None:
                    continue
                if arg in model_type_map:
                    model = model_type_map[arg]
                    if model in config:
                        config[model][arg] = val
                    else:
                        config[model] = {arg: val}
                else:
                    config[arg] = val
            plugin_input_config.plugins[plugin] = config

        plugin_configs.append(plugin_input_config)

    return plugin_configs


def process_args(
    raw_arg_input: list[str], plugin_names: list[str]
) -> tuple[list[str], dict[str, list[str]]]:
    """separate top level args from plugin args

    Args:
        raw_arg_input (list[str]): list of all arg input
        plugin_names (list[str]): list of plugin names

    Returns:
        tuple[list[str], dict[str, list[str]]]: tuple of top level args
        and dict of plugin name to plugin args
    """
    top_level_args = raw_arg_input

    try:
        plugin_arg_index = raw_arg_input.index("run-plugins")
    except ValueError:
        plugin_arg_index = -1

    plugin_arg_map = {}
    if plugin_arg_index != -1 and plugin_arg_index != len(raw_arg_input) - 1:
        top_level_args = raw_arg_input[: plugin_arg_index + 1]
        plugin_args = raw_arg_input[plugin_arg_index + 1 :]

        # handle help case
        if plugin_args == ["-h"]:
            top_level_args += plugin_args
        else:
            cur_plugin = None
            for arg in plugin_args:
                if arg in plugin_names:
                    plugin_arg_map[arg] = []
                    cur_plugin = arg
                elif cur_plugin:
                    plugin_arg_map[cur_plugin].append(arg)
    return (top_level_args, plugin_arg_map)


def build_config(
    config_reg: ConfigRegistry,
    plugin_reg: PluginRegistry,
    logger: logging.Logger,
    plugins: Optional[list[str]] = None,
    built_in_configs: Optional[list[str]] = None,
) -> PluginConfig:
    """build a plugin config

    Args:
        config_reg (ConfigRegistry): config registry instance
        plugin_reg (PluginRegistry): plugin registry instance
        logger (logging.Logger): logger instance
        plugins (Optional[list[str]], optional): list of plugin names to include. Defaults to None.
        built_in_configs (Optional[list[str]], optional): list of built in config names to include. Defaults to None.

    Returns:
        PluginConfig: plugin config obf
    """
    configs = []
    if plugins:
        logger.info("Building config for plugins: %s", plugins)
        config_builder = ConfigBuilder(plugin_registry=plugin_reg)
        configs.append(config_builder.gen_config(plugins))

    if built_in_configs:
        logger.info("Retrieving built in configs: %s", built_in_configs)
        for config in built_in_configs:
            if config not in config_reg.configs:
                logger.warning("No built in config found for name: %s", config)
            else:
                configs.append(config_reg.configs[config])

    config = PluginExecutor.merge_configs(configs)
    return config


def parse_describe(
    parsed_args: argparse.Namespace,
    plugin_reg: PluginRegistry,
    config_reg: ConfigRegistry,
    logger: logging.Logger,
):
    """parse 'describe' cmd line argument

    Args:
        parsed_args (argparse.Namespace): parsed cmd line arguments
        plugin_reg (PluginRegistry): plugin registry instance
        config_reg (ConfigRegistry): config registry instance
        logger (logging.Logger): logger instance
    """
    if not parsed_args.name:
        if parsed_args.type == "config":
            print("Available built-in configs:")  # noqa: T201
            for name in config_reg.configs:
                print(f"  {name}")  # noqa: T201
        elif parsed_args.type == "plugin":
            print("Available plugins:")  # noqa: T201
            for name in plugin_reg.plugins:
                print(f"  {name}")  # noqa: T201
        print(f"\nUsage: describe {parsed_args.type} <name>")  # noqa: T201
        sys.exit(0)

    if parsed_args.type == "config":
        if parsed_args.name not in config_reg.configs:
            logger.error("No config found for name: %s", parsed_args.name)
            sys.exit(1)
        config_model = config_reg.configs[parsed_args.name]
        print(f"Config Name: {parsed_args.name}")  # noqa: T201
        print(f"Description: {getattr(config_model, 'desc', '')}")  # noqa: T201
        print("Plugins:")  # noqa: T201
        for plugin in getattr(config_model, "plugins", []):
            print(f"\t{plugin}")  # noqa: T201

    elif parsed_args.type == "plugin":
        if parsed_args.name not in plugin_reg.plugins:
            logger.error("No plugin found for name: %s", parsed_args.name)
            sys.exit(1)
        plugin_class = plugin_reg.plugins[parsed_args.name]
        print(f"Plugin Name: {parsed_args.name}")  # noqa: T201
        print(f"Description: {getattr(plugin_class, '__doc__', '')}")  # noqa: T201

    sys.exit(0)


def parse_gen_plugin_config(
    parsed_args: argparse.Namespace,
    plugin_reg: PluginRegistry,
    config_reg: ConfigRegistry,
    logger: logging.Logger,
):
    """parse 'gen_plugin_config' cmd line argument

    Args:
        parsed_args (argparse.Namespace): parsed cmd line arguments
        plugin_reg (PluginRegistry): plugin registry instance
        config_reg (ConfigRegistry): config registry instance
        logger (logging.Logger): logger instance
    """
    try:
        config = build_config(
            config_reg, plugin_reg, logger, parsed_args.plugins, parsed_args.built_in_configs
        )

        config.name = parsed_args.config_name.split(".")[0]
        config.desc = "Auto generated config"
        output_path = os.path.join(parsed_args.output_path, parsed_args.config_name)
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(config.model_dump_json(indent=2))

        logger.info("Config saved to: %s", output_path)
        sys.exit(0)
    except Exception:
        logger.exception("Exception when building config")
        sys.exit(1)


def log_system_info(log_path: str | None, system_info: SystemInfo, logger: logging.Logger):
    """dump system info object to json log

    Args:
        log_path (str): path to log folder
        system_info (SystemInfo): system object instance
    """
    if log_path:
        try:
            with open(
                os.path.join(log_path, "system_info.json"), "w", encoding="utf-8"
            ) as log_file:
                json.dump(
                    system_info.model_dump(mode="json", exclude_none=True),
                    log_file,
                    indent=2,
                )
        except Exception as exp:
            logger.error(exp)


def main(arg_input: Optional[list[str]] = None):
    """Main entry point for the CLI

    Args:
        arg_input (Optional[list[str]], optional): list of args to parse. Defaults to None.
    """
    if arg_input is None:
        arg_input = sys.argv[1:]

    plugin_reg = PluginRegistry()
    config_reg = ConfigRegistry()
    parser, plugin_subparser_map = build_parser(plugin_reg, config_reg)

    try:
        top_level_args, plugin_arg_map = process_args(arg_input, list(plugin_subparser_map.keys()))

        parsed_args = parser.parse_args(top_level_args)

        if parsed_args.log_path and parsed_args.subcmd not in ["gen-plugin-config", "describe"]:
            log_path = os.path.join(
                parsed_args.log_path,
                f"scraper_logs_{datetime.datetime.now().strftime('%Y_%m_%d-%I_%M_%S_%p')}",
            )
            os.makedirs(log_path)
        else:
            log_path = None

        logger = setup_logger(parsed_args.log_level, log_path)
        if log_path:
            logger.info("Log path: %s", log_path)

        if parsed_args.subcmd == "describe":
            parse_describe(parsed_args, plugin_reg, config_reg, logger)

        if parsed_args.subcmd == "gen-plugin-config":
            parse_gen_plugin_config(parsed_args, plugin_reg, config_reg, logger)

        parsed_plugin_args = {}
        for plugin, plugin_args in plugin_arg_map.items():
            try:
                parsed_plugin_args[plugin] = plugin_subparser_map[plugin][0].parse_args(plugin_args)
            except Exception as e:
                logger.error("%s exception parsing args for plugin: %s", str(e), plugin)

        if not parsed_plugin_args and not parsed_args.plugin_configs:
            logger.info(
                "No plugins config args specified, running default config: %s", DEFAULT_CONFIG
            )
            plugin_configs = [DEFAULT_CONFIG]
        else:
            plugin_configs = parsed_args.plugin_configs or []

        plugin_config_inst_list = get_plugin_configs(
            plugin_config_input=plugin_configs,
            system_interaction_level=parsed_args.sys_interaction_level,
            built_in_configs=config_reg.configs,
            parsed_plugin_args=parsed_plugin_args,
            plugin_subparser_map=plugin_subparser_map,
        )

        system_info = get_system_info(parsed_args)
        log_system_info(log_path, system_info, logger)
    except Exception as e:
        parser.error(str(e))

    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=plugin_config_inst_list,
        connections=parsed_args.connection_config,
        system_info=system_info,
        log_path=log_path,
    )

    try:
        results = plugin_executor.run_queue()
        if any(result.status > ExecutionStatus.WARNING for result in results):
            sys.exit(1)
        else:
            sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C. Shutting down...")
        sys.exit(130)


if __name__ == "__main__":
    main()
