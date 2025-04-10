# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from __future__ import annotations

import copy
import logging
from collections import deque
from typing import Optional, Type

from pydantic import BaseModel

from errorscraper.constants import DEFAULT_LOGGER
from errorscraper.interfaces.connectionmanager import ConnectionManager
from errorscraper.models import PluginConfig, SystemInfo
from errorscraper.pluginregistry import PluginRegistry
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

        plugin_config = self._merge_configs(plugin_configs)

        self.global_args: dict = plugin_config.global_args

        self.plugin_queue = deque(plugin_config.plugins.items())

        self.connection_library: dict[type[ConnectionManager], ConnectionManager] = {}

        self.plugin_results = []

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
                )

        self.logger.info("System Name: %s", self.system_info.name)
        self.logger.info("System SKU: %s", self.system_info.sku)
        self.logger.info("System Platform: %s", self.system_info.platform)

        self.log_path = None

    def _merge_configs(self, plugin_configs: list[PluginConfig]) -> PluginConfig:
        merged_config = PluginConfig()
        for config in plugin_configs:
            merged_config.global_args.update(config.global_args)
            merged_config.plugins.update(config.plugins)

        return merged_config

    def run_queue(self):
        try:
            while len(self.plugin_queue) > 0:
                plugin_name, plugin_args = self.plugin_queue.popleft()
                if plugin_name not in self.plugin_registry.plugins:
                    self.logger.error("Unable to find registered plugin for name %s", plugin_name)
                    continue

                plugin_class = self.plugin_registry.plugins[plugin_name]

                init_payload = {
                    "system_info": self.system_info,
                    "logger": self.logger,
                    "queue_callback": self.plugin_queue.append,
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
                                system_info=self.system_info, logger=self.logger
                            )
                        )

                    init_payload["connection_manager"] = self.connection_library[
                        connection_manager_class
                    ]

                try:
                    plugin_inst = plugin_class(**init_payload)

                    run_payload = copy.deepcopy(plugin_args)

                    for arg in TypeUtils.get_types(plugin_class.run).keys():
                        if arg in self.global_args:
                            run_payload[arg] = self.global_args[arg]

                        # TODO
                        # enable global substitution in collection and analysis args

                    self.plugin_results.append(plugin_inst.run(**run_payload))
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
