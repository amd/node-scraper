import argparse
import json
import logging
import os
import platform
import sys
import types
from typing import Callable, Optional

from pydantic import BaseModel

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.enums import SystemInteractionLevel, SystemLocation
from errorscraper.models import DataModel, PluginConfig, SystemInfo
from errorscraper.pluginexecutor import PluginExecutor
from errorscraper.pluginregistry import PluginRegistry
from errorscraper.typeutils import TypeUtils


def build_dynamic_arg_parser(
    parser: argparse.ArgumentParser,
    func: Callable,
    class_type=type[object],
) -> dict:
    skip_args = ["self", "preserve_connection", "max_event_priority_level"]
    type_map = TypeUtils.get_func_arg_types(func, class_type)

    model_type_map = {}

    for arg, arg_types in type_map.items():
        if arg in skip_args:
            continue

        cli_arg_type = str
        for arg_type in arg_types:
            if arg_type == types.NoneType:
                # handle case where generic type has been set to None
                break

            if (
                isinstance(arg_type, type)
                and issubclass(arg_type, BaseModel)
                and not issubclass(arg_type, DataModel)
            ):
                model_args = build_model_arg_parser(parser, arg_type)
                for model_arg in model_args:
                    model_type_map[model_arg] = arg
                break

            cli_arg_type = get_cli_arg_type(arg_type)

        else:
            parser.add_argument(f"--{arg.replace('_', '-')}", type=cli_arg_type)

    return model_type_map


def build_model_arg_parser(parser: argparse.ArgumentParser, model: type[BaseModel]) -> list[str]:
    type_map = TypeUtils.get_model_types(model)
    for arg, arg_types in type_map.items():
        cli_arg_type = str
        for arg_type in arg_types:
            if arg_type == types.NoneType:
                # handle case where generic type has been set to None
                break
            cli_arg_type = get_cli_arg_type(arg_type)
        parser.add_argument(f"--{arg.replace('_', '-')}", type=cli_arg_type)
    return list(type_map.keys())


def get_cli_arg_type(arg_type):
    if arg_type is bool:
        return bool_arg
    if arg_type in [str, float, int]:
        return arg_type
    return str


def log_path_arg(log_path: str) -> str | None:
    if log_path.lower() == "none":
        return None
    return log_path


def bool_arg(input: str) -> bool:
    return input.lower() in ["true", "1", "yes"]


def system_config_arg(config_path: str) -> SystemInfo:
    with open(config_path, "r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    return SystemInfo(**data)


def plugin_config_arg(config_path: str) -> PluginConfig:
    with open(config_path, "r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    return PluginConfig(**data)


def json_arg(json_path: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    return data


def system_location_arg(system_location: str) -> SystemLocation:
    try:
        location = getattr(SystemLocation, system_location)
    except Exception as e:
        raise argparse.ArgumentTypeError("Invalid input for system location") from e

    return location


def system_interaction_arg(system_interaction: str) -> SystemInteractionLevel:
    try:
        interaction_level = getattr(SystemInteractionLevel, system_interaction)
    except Exception as e:
        raise argparse.ArgumentTypeError(
            f"Invalid input for system interaction level: {system_interaction}"
        ) from e

    return interaction_level


def build_parser(
    plugin_reg: PluginRegistry,
) -> tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]:
    parser = argparse.ArgumentParser(
        description="Error scraper CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--sys-name",
        default=platform.node(),
        help="System name",
    )

    parser.add_argument(
        "--sys-location",
        type=system_location_arg,
        choices=[e.name for e in SystemLocation],
        default="LOCAL",
        help="Location of target system",
    )

    parser.add_argument(
        "--sys-interaction-level",
        type=system_interaction_arg,
        choices=[e.name for e in SystemInteractionLevel],
        default="INTERACTIVE",
        help="Specify system interaction level, used to determine the type of actions that plugins can perform",
    )

    parser.add_argument(
        "--sys-sku",
        type=str.upper,
        required=False,
        help="Manually specify SKU of system",
    )

    parser.add_argument(
        "--sys-platform",
        type=str,
        required=False,
        help="Specify system platform",
    )

    parser.add_argument(
        "--plugin-config",
        type=plugin_config_arg,
        required=False,
        help="Path to plugin config json",
    )

    parser.add_argument(
        "--system-config",
        type=system_config_arg,
        required=False,
        help="Path to system config json",
    )

    parser.add_argument(
        "--connection-config",
        type=json_arg,
        required=False,
        help="Path to system config json",
    )

    parser.add_argument(
        "--log-path",
        default=".",
        type=log_path_arg,
        help="Specifies local path for error scraper logs",
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
            model_type_map = build_dynamic_arg_parser(
                plugin_subparser, plugin_class.run, plugin_class
            )
        except Exception as e:
            print(f"Exception building arg parsers for {plugin_name}: {str(e)}")  # noqa: T201
        plugin_subparser_map[plugin_name] = (plugin_subparser, model_type_map)

    return parser, plugin_subparser_map


def setup_logger(log_level: str, log_path: str | None) -> logging.Logger:
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
        format="%(asctime)25s %(levelname)10s %(name)25s [%(message)s]",
        datefmt="%Y-%m-%d %H:%M:%S %Z",
        handlers=handlers,
        encoding="utf-8",
    )
    logging.root.setLevel(logging.INFO)
    logging.getLogger("paramiko").setLevel(logging.ERROR)

    logger = logging.getLogger(DEFAULT_LOGGER)

    return logger


def get_system_info(args) -> SystemInfo:
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
        system_info.location = args.sys_location

    return system_info


def main(arg_input: Optional[list[str]] = None):
    if arg_input is None:
        arg_input = sys.argv[1:]
    plugin_reg = PluginRegistry()
    parser, plugin_subparser_map = build_parser(plugin_reg)
    top_level_args = arg_input

    try:
        plugin_arg_index = arg_input.index("run-plugins")
    except ValueError:
        plugin_arg_index = -1

    plugin_arg_map = {}
    if plugin_arg_index != -1 and plugin_arg_index != len(arg_input) - 1:
        top_level_args = arg_input[: plugin_arg_index + 1]
        plugin_args = arg_input[plugin_arg_index + 1 :]

        # handle help case
        if plugin_args == ["-h"]:
            top_level_args += plugin_args
        else:
            cur_plugin = None
            for arg in plugin_args:
                if arg in plugin_subparser_map.keys():
                    plugin_arg_map[arg] = []
                    cur_plugin = arg
                elif cur_plugin:
                    plugin_arg_map[cur_plugin].append(arg)

    parsed_args = parser.parse_args(top_level_args)
    logger = setup_logger(parsed_args.log_level, parsed_args.log_path)

    parsed_plugin_args = {}
    for plugin, plugin_args in plugin_arg_map.items():
        try:
            parsed_plugin_args[plugin] = plugin_subparser_map[plugin][0].parse_args(plugin_args)
        except Exception:
            logger.exception("Exception parsing args for plugin: %s", plugin)

    system_info = get_system_info(parsed_args)

    base_config = PluginConfig()

    base_config.global_args["system_interaction_level"] = parsed_args.sys_interaction_level

    plugin_configs = [base_config]

    if parsed_args.plugin_config:
        plugin_configs.append(parsed_args.plugin_config)

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

    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=plugin_configs,
        connections=parsed_args.connection_config,
        system_info=system_info,
    )

    plugin_executor.run_queue()


if __name__ == "__main__":
    main()
