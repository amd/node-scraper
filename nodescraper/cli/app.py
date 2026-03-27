###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
"""Composed CLI application: registries, parser, parse, and plugin run execution.

Hosts embed :class:`NodeScraperCliApp` (or call :func:`nodescraper.cli.main.main` with
``extensions=``). Use :func:`~nodescraper.cli.host_integration.build_cli_parser` for the stock
parser tree; use :mod:`nodescraper.cli.embed` only for in-process ``run-plugins`` mapping and
:func:`~nodescraper.cli.embed.run_cli_embedded`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
from collections.abc import Sequence
from typing import Optional

from nodescraper.cli.compare_runs import run_compare_runs
from nodescraper.cli.constants import DEFAULT_CONFIG
from nodescraper.cli.extension import CliExtension
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
    process_args,
)
from nodescraper.cli.host_integration import build_cli_parser
from nodescraper.cli.invocation import PluginRunInvocation
from nodescraper.configregistry import ConfigRegistry
from nodescraper.connection.redfish import (
    RedfishConnection,
    get_oem_diagnostic_allowable_values,
)
from nodescraper.connection.redfish.redfish_params import RedfishConnectionParams
from nodescraper.constants import DEFAULT_LOGGER
from nodescraper.enums import ExecutionStatus
from nodescraper.models import PluginConfig
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry


class NodeScraperCliApp:
    """Single entry for CLI lifecycle: registries, argparse, and plugin run."""

    def __init__(self, *, extensions: Sequence[CliExtension] = ()):
        self.extensions: tuple[CliExtension, ...] = tuple(extensions)
        self.plugin_reg = PluginRegistry()
        self.config_reg = ConfigRegistry()
        for ext in self.extensions:
            ext.prepare_registries(self.plugin_reg, self.config_reg)
        self.config_reg.configs["AllPlugins"] = PluginConfig(
            name="AllPlugins",
            desc="Run all registered plugins with default arguments",
            global_args={},
            plugins={name: {} for name in self.plugin_reg.plugins},
            result_collators={},
        )
        self.parser, self.plugin_subparser_map = build_cli_parser(
            self.plugin_reg,
            self.config_reg,
            extensions=self.extensions,
        )

    @staticmethod
    def setup_logger(log_level: str = "INFO", log_path: Optional[str] = None) -> logging.Logger:
        log_level = getattr(logging, log_level, "INFO")
        handlers: list[logging.Handler] = [logging.StreamHandler(stream=sys.stdout)]
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
        return logging.getLogger(DEFAULT_LOGGER)

    def execute_plugin_run(self, inv: PluginRunInvocation) -> int:
        """Run :class:`~nodescraper.pluginexecutor.PluginExecutor` and post-run reference config."""
        plugin_executor = PluginExecutor(
            logger=inv.logger,
            plugin_configs=inv.plugin_config_inst_list,
            connections=inv.parsed_args.connection_config,
            system_info=inv.system_info,
            log_path=inv.log_path,
            plugin_registry=inv.plugin_reg,
        )
        try:
            results = plugin_executor.run_queue()
            dump_results_to_csv(
                results, inv.sname, inv.log_path or os.getcwd(), inv.timestamp, inv.logger
            )
            if inv.parsed_args.reference_config:
                if any(result.status > ExecutionStatus.WARNING for result in results):
                    inv.logger.warning(
                        "Skipping reference config write because one or more plugins failed"
                    )
                else:
                    merged_plugin_config = PluginExecutor.merge_configs(inv.plugin_config_inst_list)
                    ref_config = generate_reference_config(
                        results,
                        inv.plugin_reg,
                        inv.logger,
                        run_plugin_config=merged_plugin_config,
                    )
                    if inv.log_path:
                        path = os.path.join(inv.log_path, "reference_config.json")
                    else:
                        path = os.path.join(os.getcwd(), "reference_config.json")
                    try:
                        with open(path, "w") as f:
                            json.dump(
                                ref_config.model_dump(mode="json", exclude_none=True),
                                f,
                                indent=2,
                            )
                        inv.logger.info("Reference config written to: %s", path)
                    except Exception as exp:
                        inv.logger.error(exp)
            if any(result.status > ExecutionStatus.WARNING for result in results):
                return 1
            return 0
        except KeyboardInterrupt:
            inv.logger.info("Received Ctrl+C. Shutting down...")
            return 130

    def main(
        self,
        arg_input: Optional[list[str]] = None,
        *,
        parsed_top_level: Optional[argparse.Namespace] = None,
        plugin_arg_map: Optional[dict[str, list[str]]] = None,
        invalid_plugins: Optional[list[str]] = None,
    ) -> None:
        """Same behavior as :func:`nodescraper.cli.main.main` (may call ``sys.exit``)."""
        parser = self.parser
        plugin_reg = self.plugin_reg
        config_reg = self.config_reg
        plugin_subparser_map = self.plugin_subparser_map

        try:
            if parsed_top_level is not None:
                parsed_args = parsed_top_level
                if plugin_arg_map is None:
                    pn = getattr(parsed_top_level, "plugin_name", None)
                    plugin_arg_map = {pn: []} if pn else {}
                if invalid_plugins is None:
                    invalid_plugins = []
            else:
                if arg_input is None:
                    arg_input = sys.argv[1:]
                top_level_args, plugin_arg_map, invalid_plugins = process_args(
                    arg_input, list(plugin_subparser_map.keys())
                )
                parsed_args = parser.parse_args(top_level_args)
            system_info = get_system_info(parsed_args)
            sname = system_info.name.lower().replace("-", "_").replace(".", "_")
            timestamp = datetime.datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")

            if parsed_args.log_path and parsed_args.subcmd not in [
                "gen-plugin-config",
                "describe",
                "compare-runs",
            ]:
                log_path = os.path.join(
                    parsed_args.log_path,
                    f"scraper_logs_{sname}_{timestamp}",
                )
                os.makedirs(log_path)
            else:
                log_path = None

            logger = self.setup_logger(parsed_args.log_level, log_path)
            if log_path:
                logger.info("Log path: %s", log_path)

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

            if parsed_args.subcmd == "compare-runs":
                run_compare_runs(
                    parsed_args.path1,
                    parsed_args.path2,
                    plugin_reg,
                    logger,
                    skip_plugins=getattr(parsed_args, "skip_plugins", None) or [],
                    include_plugins=getattr(parsed_args, "include_plugins", None),
                    truncate_message=not getattr(parsed_args, "dont_truncate", False),
                )
                sys.exit(0)

            if parsed_args.subcmd == "show-redfish-oem-allowable":
                if not parsed_args.connection_config:
                    parser.error("show-redfish-oem-allowable requires --connection-config")
                raw = parsed_args.connection_config.get("RedfishConnectionManager")
                if not raw:
                    logger.error("Connection config must contain RedfishConnectionManager")
                    sys.exit(1)
                params = RedfishConnectionParams.model_validate(raw)
                password = params.password.get_secret_value() if params.password else None
                base_url = f"{'https' if params.use_https else 'http'}://{params.host}" + (
                    f":{params.port}" if params.port else ""
                )
                conn = RedfishConnection(
                    base_url=base_url,
                    username=params.username,
                    password=password,
                    timeout=params.timeout_seconds,
                    use_session_auth=params.use_session_auth,
                    verify_ssl=params.verify_ssl,
                    api_root=params.api_root,
                )
                try:
                    conn._ensure_session()
                    allowable = get_oem_diagnostic_allowable_values(
                        conn, parsed_args.log_service_path
                    )
                    if allowable is None:
                        logger.warning(
                            "Could not read OEMDiagnosticDataType@Redfish.AllowableValues from LogService"
                        )
                        sys.exit(1)
                    print(json.dumps(allowable, indent=2))  # noqa: T201
                finally:
                    conn.close()
                sys.exit(0)

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
            for plugin, pargs in plugin_arg_map.items():
                try:
                    parsed_plugin_args[plugin] = plugin_subparser_map[plugin][0].parse_args(pargs)
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

        inv = PluginRunInvocation(
            plugin_reg=plugin_reg,
            parsed_args=parsed_args,
            plugin_config_inst_list=plugin_config_inst_list,
            system_info=system_info,
            log_path=log_path,
            logger=logger,
            timestamp=timestamp,
            sname=sname,
        )
        code = self.execute_plugin_run(inv)
        sys.exit(code)


__all__ = ["NodeScraperCliApp"]
