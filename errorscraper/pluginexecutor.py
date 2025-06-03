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
from __future__ import annotations

import copy
import logging
from collections import deque
from typing import Optional, Type

from pydantic import BaseModel

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.interfaces import ConnectionManager, DataPlugin
from errorscraper.models import PluginConfig, SystemInfo
from errorscraper.models.pluginresult import PluginResult
from errorscraper.pluginregistry import PluginRegistry
from errorscraper.taskresulthooks import FileSystemLogHook
from errorscraper.typeutils import TypeUtils


class PluginExecutor:
    """Class to manage execution of data collectors and error detectors"""

    def __init__(
        self,
        plugin_configs: list[PluginConfig],
        connections: Optional[dict[str, dict | BaseModel]] = None,
        system_info: Optional[SystemInfo] = None,
        logger: Optional[logging.Logger] = None,
        plugin_registry: Optional[PluginRegistry] = None,
        log_path: Optional[str] = None,
    ):

        if logger is None:
            logger = logging.getLogger(DEFAULT_LOGGER)
        self.logger = logger

        if plugin_registry is None:
            plugin_registry = PluginRegistry()
        self.plugin_registry = plugin_registry

        if system_info is None:
            system_info = SystemInfo()
        self.system_info = system_info

        self.plugin_config = self.merge_configs(plugin_configs)

        self.connection_library: dict[type[ConnectionManager], ConnectionManager] = {}

        self.log_path = log_path

        self.connection_result_hooks = []
        if log_path:
            self.connection_result_hooks.append(FileSystemLogHook(log_base_path=log_path))

        if connections:
            for connection, connection_args in connections.items():
                if connection not in self.plugin_registry.connection_managers:
                    self.logger.error(
                        "Unable to find registered connection manager class for %s", connection
                    )
                    continue

                connection_manager = self.plugin_registry.connection_managers[connection]

                self.connection_library[connection_manager] = connection_manager(
                    system_info=self.system_info,
                    logger=self.logger,
                    connection_args=connection_args,
                    task_result_hooks=self.connection_result_hooks,
                )

        self.logger.info("System Name: %s", self.system_info.name)
        self.logger.info("System SKU: %s", self.system_info.sku)
        self.logger.info("System Platform: %s", self.system_info.platform)
        self.logger.info("System location: %s", self.system_info.location)

    @staticmethod
    def merge_configs(plugin_configs: list[PluginConfig]) -> PluginConfig:
        merged_config = PluginConfig()
        for config in plugin_configs:
            merged_config.global_args.update(config.global_args)
            merged_config.plugins.update(config.plugins)
            merged_config.result_collators.update(config.result_collators)

        return merged_config

    def run_queue(self) -> list[PluginResult]:
        """Run the plugin queue and return results

        Returns:
            list[PluginResult]: List of results from running the plugins in the queue
        """
        plugin_results = []
        plugin_queue = deque(self.plugin_config.plugins.items())
        try:
            while len(plugin_queue) > 0:
                plugin_name, plugin_args = plugin_queue.popleft()
                if plugin_name not in self.plugin_registry.plugins:
                    self.logger.error("Unable to find registered plugin for name %s", plugin_name)
                    continue

                plugin_class = self.plugin_registry.plugins[plugin_name]

                init_payload = {
                    "system_info": self.system_info,
                    "logger": self.logger,
                    "queue_callback": plugin_queue.append,
                    "log_path": self.log_path,
                }

                if plugin_class.CONNECTION_TYPE:
                    connection_manager_class: Type[ConnectionManager] = plugin_class.CONNECTION_TYPE
                    if (
                        connection_manager_class.__name__
                        not in self.plugin_registry.connection_managers
                    ):
                        self.logger.error(
                            "Unable to find registered connection manager class for %s that is required by",
                            connection_manager_class.__name__,
                        )
                        continue

                    if connection_manager_class not in self.connection_library:
                        self.logger.info(
                            "Initializing connection manager for %s with default args",
                            connection_manager_class.__name__,
                        )
                        self.connection_library[connection_manager_class] = (
                            connection_manager_class(
                                system_info=self.system_info,
                                logger=self.logger,
                                task_result_hooks=self.connection_result_hooks,
                            )
                        )

                    init_payload["connection_manager"] = self.connection_library[
                        connection_manager_class
                    ]

                try:
                    plugin_inst = plugin_class(**init_payload)

                    run_payload = copy.deepcopy(plugin_args)

                    run_args = TypeUtils.get_func_arg_types(plugin_class.run, plugin_class)
                    for arg in run_args.keys():
                        if arg == "preserve_connection" and issubclass(plugin_class, DataPlugin):
                            run_payload[arg] = True
                        elif arg in self.plugin_config.global_args:
                            run_payload[arg] = self.plugin_config.global_args[arg]

                        # TODO
                        # enable global substitution in collection and analysis args
                    self.logger.info("-" * 50)
                    plugin_results.append(plugin_inst.run(**run_payload))
                except Exception as e:
                    self.logger.exception(
                        "Unexpected exception when running plugin %s: %s", plugin_name, e
                    )
        except Exception as e:
            self.logger.exception("Unexpected exception running plugin queue: %s", str(e))
        finally:
            self.logger.info("Closing connections")
            for connection_manager in self.connection_library.values():
                connection_manager.disconnect()

            if self.plugin_config.result_collators:
                self.logger.info("Running result collators")
                for collator, collator_args in self.plugin_config.result_collators.items():
                    collator_class = self.plugin_registry.result_collators.get(collator)
                    if collator_class is None:
                        self.logger.warning(
                            "No result collator found in registry for name: %s", collator
                        )
                        continue

                    self.logger.info("Running %s result collator", collator)
                    collator_inst = collator_class(logger=self.logger, log_path=self.log_path)
                    collator_inst.collate_results(
                        plugin_results,
                        [
                            connection_manager.result
                            for connection_manager in self.connection_library.values()
                        ],
                        **collator_args,
                    )

        return plugin_results
