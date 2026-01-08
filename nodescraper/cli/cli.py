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
from importlib import import_module
from typing import Optional

import nodescraper
from nodescraper.cli.constants import DEFAULT_CONFIG, META_VAR_MAP
from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.cli.helper import (
    dump_results_to_csv,
    generate_reference_config,
    generate_reference_config_from_logs,
    generate_summary,
    get_plugin_configs,
    get_system_info,
    log_system_info,
    parse_describe,
    parse_gen_plugin_config,
)
from nodescraper.cli.inputargtypes import ModelArgHandler, json_arg, log_path_arg
from nodescraper.configregistry import ConfigRegistry
from nodescraper.constants import DEFAULT_LOGGER
from nodescraper.enums import ExecutionStatus, SystemInteractionLevel, SystemLocation
from nodescraper.models import SystemInfo
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry


def discover_external_plugins():
    """Discover ext_nodescraper_plugins from all installed packages.

    Returns:
        list: List of discovered plugin packages
    """
    extra_pkgs = []
    seen_paths = set()  # Track paths to avoid duplicates

    try:
        import ext_nodescraper_plugins as ext_pkg

        extra_pkgs.append(ext_pkg)
        if hasattr(ext_pkg, "__file__") and ext_pkg.__file__:
            seen_paths.add(ext_pkg.__file__)
    except ImportError:
        pass

    # Discover ext_nodescraper_plugins from installed packages
    try:
        from importlib.metadata import distributions

        for dist in distributions():
            pkg_name = dist.metadata.get("Name", "")
            if not pkg_name:
                continue

            name_variants = [
                pkg_name.replace("-", "_"),
                pkg_name.replace("_", "-"),
            ]

            try:
                top_level = dist.read_text("top_level.txt")
                if top_level:
                    name_variants.extend(top_level.strip().split("\n"))
            except Exception:
                pass

            for variant in name_variants:
                if not variant:
                    continue

                try:
                    module_path = f"{variant}.ext_nodescraper_plugins"
                    ext_pkg = import_module(module_path)

                    # Check if we already have this package (by file path)
                    pkg_path = getattr(ext_pkg, "__file__", None)
                    if pkg_path and pkg_path in seen_paths:
                        continue

                    # Add the package
                    extra_pkgs.append(ext_pkg)
                    if pkg_path:
                        seen_paths.add(pkg_path)

                    break

                except (ImportError, AttributeError, ModuleNotFoundError):
                    continue

    except Exception:
        pass

    return extra_pkgs


extra_pkgs = discover_external_plugins()


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
        "--version",
        action="version",
        version=f"%(prog)s {nodescraper.__version__}",
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

    parser.add_argument(
        "--gen-reference-config",
        dest="reference_config",
        action="store_true",
        help="Generate reference config from system. Writes to ./reference_config.json.",
    )

    parser.add_argument(
        "--skip-sudo",
        dest="skip_sudo",
        action="store_true",
        help="Skip plugins that require sudo permissions",
    )

    subparsers = parser.add_subparsers(dest="subcmd", help="Subcommands")

    summary_parser = subparsers.add_parser(
        "summary",
        help="Generates summary csv file",
    )

    summary_parser.add_argument(
        "--search-path",
        dest="search_path",
        type=log_path_arg,
        help="Path to node-scraper previously generated results.",
    )

    summary_parser.add_argument(
        "--output-path",
        dest="output_path",
        type=log_path_arg,
        help="Specifies path for summary.csv.",
    )

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
        "--gen-reference-config-from-logs",
        dest="reference_config_from_logs",
        type=log_path_arg,
        help="Generate reference config from previous run logfiles. Writes to --output-path/reference_config.json if provided, otherwise ./reference_config.json.",
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
            continue
        plugin_subparser_map[plugin_name] = (plugin_subparser, model_type_map)

    return parser, plugin_subparser_map


def setup_logger(log_level: str = "INFO", log_path: Optional[str] = None) -> logging.Logger:
    """set up root logger when using the CLI

    Args:
        log_level (str): log level to use
        log_path (Optional[str]): optional path to filesystem log location

    Returns:
        logging.Logger: logger intstance
    """
    log_level = getattr(logging, log_level, "INFO")

    handlers = [logging.StreamHandler(stream=sys.stdout)]

    if log_path:
        log_file_name = os.path.join(log_path, "nodescraper.log")
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
    invalid_plugins = []
    if plugin_arg_index != -1 and plugin_arg_index != len(raw_arg_input) - 1:
        top_level_args = raw_arg_input[: plugin_arg_index + 1]
        plugin_args = raw_arg_input[plugin_arg_index + 1 :]

        # handle help case
        if plugin_args == ["-h"]:
            top_level_args += plugin_args
        else:
            cur_plugin = None
            for arg in plugin_args:
                # Handle comma-separated plugin names (but not arguments)
                if not arg.startswith("-") and "," in arg:
                    # Split comma-separated plugin names
                    for potential_plugin in arg.split(","):
                        potential_plugin = potential_plugin.strip()
                        if potential_plugin in plugin_names:
                            plugin_arg_map[potential_plugin] = []
                            cur_plugin = potential_plugin
                        elif potential_plugin:
                            # Track invalid plugin names to log event later
                            invalid_plugins.append(potential_plugin)
                elif arg in plugin_names:
                    plugin_arg_map[arg] = []
                    cur_plugin = arg
                elif cur_plugin:
                    plugin_arg_map[cur_plugin].append(arg)
                elif not arg.startswith("-"):
                    # Track invalid plugin names to log event later
                    invalid_plugins.append(arg)
    return (top_level_args, plugin_arg_map, invalid_plugins)


def main(arg_input: Optional[list[str]] = None):
    """Main entry point for the CLI

    Args:
        arg_input (Optional[list[str]], optional): list of args to parse. Defaults to None.
    """
    if arg_input is None:
        arg_input = sys.argv[1:]

    plugin_reg = PluginRegistry(plugin_pkg=extra_pkgs)

    config_reg = ConfigRegistry()
    parser, plugin_subparser_map = build_parser(plugin_reg, config_reg)

    try:
        top_level_args, plugin_arg_map, invalid_plugins = process_args(
            arg_input, list(plugin_subparser_map.keys())
        )

        parsed_args = parser.parse_args(top_level_args)
        system_info = get_system_info(parsed_args)
        sname = system_info.name.lower().replace("-", "_").replace(".", "_")
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")

        if parsed_args.log_path and parsed_args.subcmd not in ["gen-plugin-config", "describe"]:
            log_path = os.path.join(
                parsed_args.log_path,
                f"scraper_logs_{sname}_{timestamp}",
            )
            os.makedirs(log_path)
        else:
            log_path = None

        logger = setup_logger(parsed_args.log_level, log_path)
        if log_path:
            logger.info("Log path: %s", log_path)

        # Log warning if invalid plugin names were provided
        if invalid_plugins:
            logger.warning(
                "Invalid plugin name(s) ignored: %s. Use 'describe plugin' to list available plugins.",
                ", ".join(invalid_plugins),
            )

        if parsed_args.subcmd == "summary":
            generate_summary(parsed_args.search_path, parsed_args.output_path, logger)
            sys.exit(0)

        if parsed_args.subcmd == "describe":
            parse_describe(parsed_args, plugin_reg, config_reg, logger)

        if parsed_args.subcmd == "gen-plugin-config":

            if parsed_args.reference_config_from_logs:
                ref_config = generate_reference_config_from_logs(
                    parsed_args.reference_config_from_logs, plugin_reg, logger
                )
                output_path = os.getcwd()
                if parsed_args.output_path:
                    output_path = parsed_args.output_path
                path = os.path.join(output_path, "reference_config.json")
                try:
                    with open(path, "w") as f:
                        json.dump(
                            ref_config.model_dump(mode="json", exclude_none=True),
                            f,
                            indent=2,
                        )
                        logger.info("Reference config written to: %s", path)
                except Exception as exp:
                    logger.error(exp)
                sys.exit(0)

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

        if parsed_args.skip_sudo:
            plugin_config_inst_list[-1].global_args.setdefault("collection_args", {})[
                "skip_sudo"
            ] = True

        log_system_info(log_path, system_info, logger)
    except Exception as e:
        parser.error(str(e))

    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=plugin_config_inst_list,
        connections=parsed_args.connection_config,
        system_info=system_info,
        log_path=log_path,
        plugin_registry=plugin_reg,
    )

    try:
        results = plugin_executor.run_queue()

        dump_results_to_csv(results, sname, log_path, timestamp, logger)

        if parsed_args.reference_config:
            ref_config = generate_reference_config(results, plugin_reg, logger)
            if log_path:
                path = os.path.join(log_path, "reference_config.json")
            else:
                path = os.path.join(os.getcwd(), "reference_config.json")
            try:
                with open(path, "w") as f:
                    json.dump(
                        ref_config.model_dump(mode="json", exclude_none=True),
                        f,
                        indent=2,
                    )
                    logger.info("Reference config written to: %s", path)
            except Exception as exp:
                logger.error(exp)

        if any(result.status > ExecutionStatus.WARNING for result in results):
            sys.exit(1)
        else:
            sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C. Shutting down...")
        sys.exit(130)


if __name__ == "__main__":
    main()
