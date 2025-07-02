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
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from nodescraper.cli.inputargtypes import ModelArgHandler
from nodescraper.configbuilder import ConfigBuilder
from nodescraper.configregistry import ConfigRegistry
from nodescraper.enums import SystemInteractionLevel, SystemLocation
from nodescraper.models import PluginConfig, PluginResult, SystemInfo, TaskResult
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.resultcollators.tablesummary import TableSummary


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


def generate_reference_config(
    results: list[PluginResult], plugin_reg: PluginRegistry, logger: logging.Logger
) -> PluginConfig:
    """Generate reference config from plugin results

    Args:
        results (list[PluginResult]): list of plugin results
        plugin_reg (PluginRegistry): registry containing all registered plugins
        logger (logging.Logger): logger

    Returns:
        PluginConfig: holds model that defines final reference config
    """
    plugin_config = PluginConfig()
    plugins = {}
    for obj in results:
        data_model = obj.result_data.system_data

        plugin = plugin_reg.plugins.get(obj.result_data.collection_result.parent)
        if not plugin.ANALYZER_ARGS:
            logger.warning(
                "Plugin: %s does not support reference config creation. No analyzer args defined.",
                obj.source,
            )
            continue

        args = None
        try:
            args = plugin.ANALYZER_ARGS.build_from_model(data_model)
        except NotImplementedError as nperr:
            logger.info(nperr)
            continue
        args.build_from_model(data_model)
        plugins[obj.source] = {"analysis_args": {}}
        plugins[obj.source]["analysis_args"] = args.model_dump(exclude_none=True)
    plugin_config.plugins = plugins

    return plugin_config


def generate_reference_config_from_logs(path, plugin_reg, logger):
    found = find_datamodel_and_result(path)
    plugin_config = PluginConfig()
    plugins = {}
    for dm, res in found:
        result_path = Path(res)
        res_payload = json.loads(result_path.read_text(encoding="utf-8"))
        task_res = TaskResult(**res_payload)
        # print(json.dumps(res_payload, indent=2))
        # print(task_res.parent)
        dm_path = Path(dm)
        dm_payload = json.loads(dm_path.read_text(encoding="utf-8"))
        plugin = plugin_reg.plugins.get(task_res.parent)
        data_model = plugin.DATA_MODEL.model_validate(dm_payload)

        if not plugin.ANALYZER_ARGS:
            logger.warning(
                "Plugin: %s does not support reference config creation. No analyzer args defined.",
                task_res.parent,
            )
            continue

        args = None

        try:
            args = plugin.ANALYZER_ARGS.build_from_model(data_model)
        except NotImplementedError as nperr:
            logger.info(nperr)
            continue
        plugins[task_res.parent] = {"analysis_args": {}}
        plugins[task_res.parent]["analysis_args"] = args.model_dump(exclude_none=True)

        # print("Datamodel:", dm)
        # print("Result:   ", res)
    plugin_config.plugins = plugins
    return plugin_config


def find_datamodel_and_result(base_path: str) -> list[Tuple[str, str]]:
    """ """
    tuple_list: list[Tuple[str, str, str]] = []
    for root, _, files in os.walk(base_path):
        if "collector" in os.path.basename(root).lower():
            datamodel_path = None
            result_path = None

            for fname in files:
                low = fname.lower()
                if low.endswith("datamodel.json"):
                    datamodel_path = os.path.join(root, fname)
                elif low == "result.json":
                    result_path = os.path.join(root, fname)

            if datamodel_path and result_path:
                tuple_list.append((datamodel_path, result_path))

    return tuple_list
