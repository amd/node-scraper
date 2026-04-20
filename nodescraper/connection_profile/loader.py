# Copyright (C) 2026 Advanced Micro Devices, Inc. All rights reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ConnectionProfileLoader(ABC):
    """Load connection-related settings from a JSON file into an object for plugin runs.

    Node-scraper does not interpret the file contents; implementations live in other
    distributions and are registered via importlib entry points.
    """

    @abstractmethod
    def load(self, path: Path) -> object:
        """Read ``path`` and return an object suitable for :attr:`PluginRunInvocation.host_cli_args`.

        Implementations may also attach a ``connection_config`` dict (same shape as
        ``--connection-config``) for :class:`~nodescraper.pluginexecutor.PluginExecutor`.
        """
