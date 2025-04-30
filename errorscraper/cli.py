import argparse
import datetime
import json
import logging
import os
import platform
import sys
import types
from typing import Callable, Generic, Optional, Type

from pydantic import BaseModel, ValidationError

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.enums import SystemInteractionLevel, SystemLocation
from errorscraper.generictypes import TModelType
from errorscraper.models import DataModel, PluginConfig, SystemInfo
from errorscraper.pluginexecutor import PluginExecutor
from errorscraper.pluginregistry import PluginRegistry
from errorscraper.resultcollators.tablesummary import TableSummary
from errorscraper.typeutils import TypeUtils


class DynamicParserBuilder:
    """Dynamically build an argparse parser based on function type annotations or pydantic model types"""

    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser

    def add_func_args(self, func: Callable, class_type: Optional[Type[object]] = None) -> dict:
        """Add parser argument based on arguments in a function signature

        Args:
            func (Callable): function to analyze
            class_type (Optional[Type[object]], optional): Class which function belongs to. Defaults to None.

        Returns:
            dict: dictionary containing mapping of parser args which were added from pydantic model args in the function
        """
        skip_args = ["self", "preserve_connection", "max_event_priority_level"]
        type_map = TypeUtils.get_func_arg_types(func, class_type)

        model_type_map = {}

        for arg, arg_data in type_map.items():
            if arg in skip_args:
                continue

            type_class_map = {
                type_class.type_class: type_class for type_class in arg_data.type_classes
            }

            # handle case where generic type has been set to None
            if types.NoneType in type_class_map and len(arg_data.type_classes) == 1:
                continue

            model_arg = self.get_model_arg(type_class_map)

            # only add cli args for top level model args
            if model_arg:
                model_args = self.build_model_arg_parser(model_arg, arg_data.required)
                for model_arg in model_args:
                    model_type_map[model_arg] = arg
            else:
                self.add_argument(type_class_map, arg.replace("_", "-"), arg_data.required)

        return model_type_map

    @classmethod
    def get_model_arg(cls, type_class_map: dict) -> Type[BaseModel] | None:
        """Get the first type which is a pydantic model from a type class map

        Args:
            type_class_map (dict): mapping of type classes

        Returns:
            Type[BaseModel] | None: pydantic model type
        """
        return next(
            (
                type_class
                for type_class in type_class_map
                if (
                    isinstance(type_class, type)
                    and issubclass(type_class, BaseModel)
                    and not issubclass(type_class, DataModel)
                )
            ),
            None,
        )

    def add_argument(
        self,
        type_class_map: dict,
        arg_name: str,
        required: bool,
    ) -> None:
        """Add an argument to a parser with an appropriate type

        Args:
            type_class_map (dict): type classes for the arg
            arg_name (str): argument name
            required (bool): whether or not the arg is required
        """
        if list in type_class_map:
            type_class = type_class_map[list]
            self.parser.add_argument(
                f"--{arg_name}",
                nargs="*",
                type=type_class.inner_type if type_class.inner_type else str,
                required=required,
            )
        elif bool in type_class_map:
            self.parser.add_argument(f"--{arg_name}", type=bool_arg, required=required)
        elif float in type_class_map:
            self.parser.add_argument(f"--{arg_name}", type=float, required=required)
        elif int in type_class_map:
            self.parser.add_argument(f"--{arg_name}", type=int, required=required)
        elif dict in type_class_map or self.get_model_arg(type_class_map):
            self.parser.add_argument(f"--{arg_name}", type=dict_arg, required=required)
        else:
            self.parser.add_argument(f"--{arg_name}", type=str, required=required)

    def build_model_arg_parser(self, model: type[BaseModel], required: bool) -> list[str]:
        """Add args to a parser based on attributes of a pydantic model

        Args:
            model (type[BaseModel]): input model
            required (bool): whether the args from the model are required

        Returns:
            list[str]: list of model attributes that were added as args to the parser
        """
        type_map = TypeUtils.get_model_types(model)

        for attr, attr_data in type_map.items():
            type_class_map = {
                type_class.type_class: type_class for type_class in attr_data.type_classes
            }

            if types.NoneType in type_class_map and len(attr_data.type_classes) == 1:
                continue

            self.add_argument(type_class_map, attr.replace("_", "-"), required)

        return list(type_map.keys())


def log_path_arg(log_path: str) -> str | None:
    """Type function for a log path arg, allows 'none' to be specified to disable logging

    Args:
        log_path (str): log path string

    Returns:
        str | None: log path or None
    """
    if log_path.lower() == "none":
        return None
    return log_path


def bool_arg(str_input: str) -> bool:
    """Converts a string arg input into a bool

    Args:
        str_input (str): string input

    Returns:
        bool: bool value for string
    """
    return str_input.lower() in ["true", "1", "yes"]


def dict_arg(str_input: str) -> dict:
    """converts a json string into a dict

    Args:
        str_input (str): input string

    Raises:
        argparse.ArgumentTypeError: it error was seen when loading string into json dict

    Returns:
        dict: dict representation of the json string
    """
    try:
        return json.loads(str_input)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError("Invalid json input for arg") from e


class ModelArgHandler(Generic[TModelType]):
    """Class to handle loading json files into pydantic models"""

    def __init__(self, model: Type[TModelType]) -> types.NoneType:
        self.model = model

    def process_file_arg(self, file_path: str) -> TModelType:
        """load a json file into a pydantic model

        Args:
            file_path (str): json file path

        Raises:
            argparse.ArgumentTypeError: If validation errors were seen when building model

        Returns:
            TModelType: model instance
        """
        data = json_arg(file_path)
        try:
            return self.model(**data)
        except ValidationError as e:
            raise argparse.ArgumentTypeError(
                f"Validation errors when processing {file_path}: {e.errors()}"
            ) from e


def json_arg(json_path: str) -> dict:
    """loads a json file into a dict

    Args:
        json_path (str): path to json file

    Raises:
        argparse.ArgumentTypeError: If file does not exist or could not be decoded

    Returns:
        dict: output dict
    """
    try:
        with open(json_path, "r", encoding="utf-8") as input_file:
            data = json.load(input_file)
        return data
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"File {json_path} contains invalid JSON") from e
    except FileNotFoundError as e:
        raise argparse.ArgumentTypeError(f"Unable to find file: {json_path}") from e


def build_parser(
    plugin_reg: PluginRegistry,
) -> tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]:
    """Build an argument parser

    Args:
        plugin_reg (PluginRegistry): registry of plugins

    Returns:
        tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]: tuple containing main
        parser and subparsers for each plugin module
    """
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
    )

    parser.add_argument(
        "--sys-platform",
        type=str,
        required=False,
        help="Specify system platform",
    )

    parser.add_argument(
        "--plugin-config",
        type=ModelArgHandler(PluginConfig).process_file_arg,
        required=False,
        help="Path to plugin config json",
    )

    parser.add_argument(
        "--system-config",
        type=ModelArgHandler(SystemInfo).process_file_arg,
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
            parser_builder = DynamicParserBuilder(plugin_subparser)
            model_type_map = parser_builder.add_func_args(plugin_class.run, plugin_class)
        except Exception as e:
            print(f"Exception building arg parsers for {plugin_name}: {str(e)}")  # noqa: T201
        plugin_subparser_map[plugin_name] = (plugin_subparser, model_type_map)

    return parser, plugin_subparser_map


def setup_logger(log_level: str, log_path: str | None) -> logging.Logger:
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
    top_level_args: argparse.Namespace,
    parsed_plugin_args: dict[str, argparse.Namespace],
    plugin_subparser_map: dict[str, tuple[argparse.ArgumentParser, dict]],
) -> list[PluginConfig]:
    try:
        system_interaction_level = getattr(
            SystemInteractionLevel, top_level_args.sys_interaction_level
        )
    except Exception as e:
        raise argparse.ArgumentTypeError("Invalid input for system interaction level") from e

    base_config = PluginConfig(result_collators={str(TableSummary.__name__): {}})

    base_config.global_args["system_interaction_level"] = system_interaction_level

    plugin_configs = [base_config]

    if top_level_args.plugin_config:
        plugin_configs.append(top_level_args.plugin_config)

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


def main(arg_input: Optional[list[str]] = None):
    if arg_input is None:
        arg_input = sys.argv[1:]
    plugin_reg = PluginRegistry()
    parser, plugin_subparser_map = build_parser(plugin_reg)

    top_level_args, plugin_arg_map = process_args(arg_input, list(plugin_subparser_map.keys()))

    parsed_args = parser.parse_args(top_level_args)

    if parsed_args.log_path:
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

    parsed_plugin_args = {}
    for plugin, plugin_args in plugin_arg_map.items():
        try:
            parsed_plugin_args[plugin] = plugin_subparser_map[plugin][0].parse_args(plugin_args)
        except Exception:
            logger.exception("Exception parsing args for plugin: %s", plugin)

    system_info = get_system_info(parsed_args)

    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=get_plugin_configs(parsed_args, parsed_plugin_args, plugin_subparser_map),
        connections=parsed_args.connection_config,
        system_info=system_info,
        log_path=log_path,
    )

    plugin_executor.run_queue()


if __name__ == "__main__":
    main()
