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
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel

from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.redfish.redfish_manager import RedfishConnectionManager
from nodescraper.enums import SystemLocation
from nodescraper.interfaces import ConnectionManager, PluginInterface
from nodescraper.models import SystemInfo


def _host_from_connection_args(raw: Optional[Union[dict[str, Any], BaseModel]]) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        for key in ("host", "hostname", "ip"):
            value = raw.get(key)
            if value:
                return str(value)
        return None
    for key in ("host", "hostname", "ip"):
        value = getattr(raw, key, None)
        if value is not None and str(value):
            return str(value)
    return None


def format_in_band_target_summary(
    system_info: SystemInfo,
    connection_configs: Optional[dict[str, Union[dict[str, Any], BaseModel]]] = None,
) -> str:
    """Return a short summary of the default in-band execution target."""
    if system_info.location == SystemLocation.REMOTE:
        host = _host_from_connection_args((connection_configs or {}).get("InBandConnectionManager"))
        if host:
            return f"In-band default: remote host via SSH ({host})"
        return "In-band default: remote host via SSH"
    host_name = system_info.name or "local host"
    return f"In-band default: local host ({host_name})"


def format_plugin_execution_target(
    plugin_class: type[PluginInterface],
    *,
    system_info: SystemInfo,
    connection_manager: Optional[ConnectionManager] = None,
    connection_configs: Optional[dict[str, Union[dict[str, Any], BaseModel]]] = None,
) -> Optional[str]:
    """Return a one-line description of where a plugin collects data from."""
    connection_type = getattr(plugin_class, "CONNECTION_TYPE", None)
    if connection_type is None:
        return None

    configs = connection_configs or {}
    manager_args = (
        getattr(connection_manager, "connection_args", None) if connection_manager else None
    )

    if connection_type is RedfishConnectionManager or issubclass(
        connection_type, RedfishConnectionManager
    ):
        host = _host_from_connection_args(manager_args) or _host_from_connection_args(
            configs.get("RedfishConnectionManager")
        )
        if host:
            return f"Execution target: BMC via Redfish OOB ({host})"
        return "Execution target: BMC via Redfish OOB"

    if connection_type is InBandConnectionManager or issubclass(
        connection_type, InBandConnectionManager
    ):
        if system_info.location == SystemLocation.REMOTE:
            host = _host_from_connection_args(manager_args) or _host_from_connection_args(
                configs.get("InBandConnectionManager")
            )
            if host:
                return f"Execution target: remote host via SSH ({host})"
            return "Execution target: remote host via SSH"
        host_name = system_info.name or "local host"
        return f"Execution target: local host ({host_name})"

    return f"Execution target: {connection_type.__name__}"
