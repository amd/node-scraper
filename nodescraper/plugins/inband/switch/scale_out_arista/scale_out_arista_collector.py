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

import json
import re
from typing import Dict, List, Optional, Union

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_details, get_exception_traceback

from .collector_args import ScaleOutAristaCollectorArgs
from .scaleoutaristadata import (
    AristaBinsCounters,
    AristaCountersErrors,
    AristaDroppedPacketCounters,
    AristaDropPrecedenceCounters,
    AristaEcnCounters,
    AristaIpCounters,
    AristaNeighbors,
    AristaPacketCounters,
    AristaPauseFrameCounters,
    AristaPerQueueCounters,
    AristaPfcCounters,
    AristaPortStatus,
    AristaRatesCounters,
    AristaSystemEnv,
    AristaVersion,
    PortData,
    ScaleOutAristaDataModel,
)


class ScaleOutAristaCollector(
    InBandDataCollector[ScaleOutAristaDataModel, ScaleOutAristaCollectorArgs]
):
    """Collect Arista switch data.

    Runs Arista EOS ``show`` commands (JSON and text) and parses their
    output into a :class:`ScaleOutAristaDataModel`.
    """

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX, OSFamily.UNKNOWN}

    DATA_MODEL = ScaleOutAristaDataModel

    # When set (via the ``html_view`` collector arg), each ``| json`` command
    # is followed by its non-JSON version for human-readable artifact output.
    _html_view: bool = False

    CMD_VERSION = "show version | json | no-more"
    CMD_LLDP_NEIGHBORS = "show lldp neighbors | json | no-more"
    CMD_SYSTEM_ENV = "show system environment cooling | json | no-more"
    CMD_PORT_STATUS = "show interfaces status | json | no-more"
    CMD_ERROR_COUNTERS = "show interfaces counters errors | json | no-more"
    CMD_PACKET_COUNTERS = "show interfaces counters | json | no-more"
    CMD_BINS_COUNTERS = "show interfaces counters bins | json | no-more"
    CMD_IP_COUNTERS = "show interfaces counters ip | json | no-more"
    CMD_RATES_COUNTERS = "show interfaces counters rates | json | no-more"
    CMD_PFC_COUNTERS = "show priority-flow-control counters | json | no-more"
    CMD_DROPPED_PACKET_COUNTERS = "show interfaces counters queue | no-more"
    CMD_DROP_PRECEDENCE_COUNTERS = "show interfaces counters queue drop-precedence | no-more"
    CMD_PER_QUEUE_COUNTERS = "show interfaces counters queue detail | no-more"
    CMD_PAUSE_FRAME_COUNTERS = "show interfaces flow-control | json | no-more"
    CMD_ECN_COUNTERS = "show qos interfaces ecn counters queue | json | no-more"

    # Commands run for diagnostics, not parsed into a data model.
    CMD_RUNNING_CONFIG = "show running-config | no-more"
    CMD_STARTUP_CONFIG = "show startup-config | no-more"
    CMD_IP_INTERFACE = "show ip interface | no-more"
    CMD_INTERFACES_PHY = "show interfaces phy | no-more"
    CMD_INTERFACES_PHY_DETAIL = "show interfaces phy detail | no-more"
    CMD_QOS_PROFILE = "show qos profile | no-more"
    CMD_QOS_PROFILE_SUMMARY = "show qos profile summary | no-more"
    CMD_QOS_MAPS = "show qos maps | no-more"
    CMD_QOS_INTERFACES = "show qos interfaces | no-more"
    CMD_QOS_INTERFACES_TRUST = "show qos interfaces trust | no-more"
    CMD_PFC_STATUS = "show priority-flow-control status | no-more"
    CMD_QOS_INTERFACES_ECN = "show qos interfaces ecn | no-more"
    CMD_LLDP = "show lldp | no-more"
    CMD_TRIDENT_MMU_QUEUE_STATUS = "show platform trident mmu queue status | no-more"

    # Aggregate of the diagnostic CMD_* commands above.
    ARTIFACT_COMMANDS: list[str] = [
        CMD_RUNNING_CONFIG,
        CMD_STARTUP_CONFIG,
        CMD_IP_INTERFACE,
        CMD_INTERFACES_PHY,
        CMD_INTERFACES_PHY_DETAIL,
        CMD_QOS_PROFILE,
        CMD_QOS_PROFILE_SUMMARY,
        CMD_QOS_MAPS,
        CMD_QOS_INTERFACES,
        CMD_QOS_INTERFACES_TRUST,
        CMD_PFC_STATUS,
        CMD_QOS_INTERFACES_ECN,
        CMD_LLDP,
        CMD_TRIDENT_MMU_QUEUE_STATUS,
    ]

    # helpers
    def _run_arista_json(self, command: str) -> Optional[Union[dict, list]]:
        """Run an Arista EOS command returning JSON.

        Args:
            command: The full EOS command (already including ``| json | no-more``).

        Returns:
            Parsed JSON (dict or list), or ``None`` if the call failed.
        """
        cmd_ret: CommandArtifact = self._run_sut_cmd(command)
        # After sending the JSON version, also send the non-JSON version when
        # the html_view flag is set so readable output is captured too.
        self._collect_html_view(command)
        if cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.SWITCH,
                description=f"Error running Arista command: `{command}`",
                data={
                    "command": command,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        try:
            return json.loads(cmd_ret.stdout)
        except json.JSONDecodeError as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description=f"Error parsing JSON from Arista command: `{command}`",
                data={
                    "command": command,
                    "exception": get_exception_traceback(e),
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None

    def _run_arista_text(self, command: str) -> Optional[str]:
        """Run an Arista EOS command returning text.

        Args:
            command: The full EOS command (already including ``| no-more``).

        Returns:
            The stdout text, or ``None`` if the call failed.
        """
        cmd_ret: CommandArtifact = self._run_sut_cmd(command)
        if cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.SWITCH,
                description=f"Error running Arista command: `{command}`",
                data={
                    "command": command,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        return cmd_ret.stdout or None

    # sub-collectors

    def get_version(self) -> Optional[AristaVersion]:
        """Collect version information via ``show version | json``."""
        data = self._run_arista_json(self.CMD_VERSION)
        if not isinstance(data, dict):
            return None
        try:
            return AristaVersion(**data)
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Failed to build AristaVersion model",
                data=get_exception_details(e),
                priority=EventPriority.WARNING,
            )
            return None

    @staticmethod
    def _expand_port_name(short_name: str) -> str:
        """Expand abbreviated port names like ``Et1/1`` to ``Ethernet1/1``.

        If the name already starts with ``Ethernet``, it is returned as-is.
        """
        if short_name.startswith("Et") and not short_name.startswith("Ethernet"):
            return "Ethernet" + short_name[2:]
        return short_name

    def get_port_status(self) -> Optional[Dict[str, AristaPortStatus]]:
        """Collect per-port status via ``show interfaces status | json | no-more``.

        Returns:
            Mapping of port name to :class:`AristaPortStatus`, or ``None``.
        """
        data = self._run_arista_json(self.CMD_PORT_STATUS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceStatuses", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces status' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaPortStatus] = {}
        for port_name, port_data in interfaces.items():
            # Restrict to Ethernet ports, matching the other per-port collectors.
            if not isinstance(port_data, dict) or not port_name.startswith("Ethernet"):
                continue
            try:
                result[port_name] = AristaPortStatus(**port_data)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaPortStatus for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_lldp_neighbors(self) -> Optional[AristaNeighbors]:
        """Collect LLDP neighbor info via ``show lldp neighbors | json | no-more``."""
        data = self._run_arista_json(self.CMD_LLDP_NEIGHBORS)
        if not isinstance(data, dict):
            return None
        try:
            return AristaNeighbors(**data)
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Failed to build AristaNeighbors model",
                data=get_exception_details(e),
                priority=EventPriority.WARNING,
            )
            return None

    def get_system_env(self) -> Optional[AristaSystemEnv]:
        """Collect system environment via ``show system environment cooling | json | no-more``."""
        data = self._run_arista_json(self.CMD_SYSTEM_ENV)
        if not isinstance(data, dict):
            return None
        # Extract inner fan configurations from slot wrappers.
        # Each slot has a "fans" list of individual fan config dicts.
        ps_fans: list = []
        for slot in data.get("powerSupplySlots", []) or []:
            if not isinstance(slot, dict):
                continue
            for fan in slot.get("fans", []) or []:
                if isinstance(fan, dict):
                    ps_fans.append(fan)
        data["powerSupplySlots"] = ps_fans

        ft_fans: list = []
        for slot in data.get("fanTraySlots", []) or []:
            if not isinstance(slot, dict):
                continue
            for fan in slot.get("fans", []) or []:
                if isinstance(fan, dict):
                    ft_fans.append(fan)
        data["fanTraySlots"] = ft_fans

        try:
            return AristaSystemEnv(**data)
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Failed to build AristaSystemEnv model",
                data=get_exception_details(e),
                priority=EventPriority.WARNING,
            )
            return None

    def get_error_counters(self) -> Optional[Dict[str, AristaCountersErrors]]:
        """Collect error counters via ``show interfaces counters errors | json | no-more``."""
        data = self._run_arista_json(self.CMD_ERROR_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceErrorCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces counters errors' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaCountersErrors] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaCountersErrors(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaCountersErrors for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_packet_counters(self) -> Optional[Dict[str, AristaPacketCounters]]:
        """Collect packet counters via ``show interfaces counters | json | no-more``."""
        data = self._run_arista_json(self.CMD_PACKET_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces counters' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaPacketCounters] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaPacketCounters(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaPacketCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_bins_counters(
        self,
    ) -> tuple[Optional[Dict[str, AristaBinsCounters]], Optional[Dict[str, AristaBinsCounters]]]:
        """Collect bins counters via ``show interfaces counters bins | json | no-more``.

        Returns:
            Tuple of ``(out_bins, in_bins)`` dicts keyed by port name.
        """
        data = self._run_arista_json(self.CMD_BINS_COUNTERS)
        if not isinstance(data, dict):
            return None, None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces counters bins' output",
                priority=EventPriority.WARNING,
            )
            return None, None
        out_bins: Dict[str, AristaBinsCounters] = {}
        in_bins: Dict[str, AristaBinsCounters] = {}
        for port_name, counters in interfaces.items():
            if not isinstance(counters, dict):
                continue
            out_data = counters.get("outBinsCounters")
            in_data = counters.get("inBinsCounters")
            if out_data:
                try:
                    out_bins[port_name] = AristaBinsCounters(**out_data)
                except (ValidationError, TypeError) as e:
                    self._log_event(
                        category=EventCategory.SWITCH,
                        description=f"Failed to build out AristaBinsCounters for {port_name}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
            if in_data:
                try:
                    in_bins[port_name] = AristaBinsCounters(**in_data)
                except (ValidationError, TypeError) as e:
                    self._log_event(
                        category=EventCategory.SWITCH,
                        description=f"Failed to build in AristaBinsCounters for {port_name}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
        return out_bins or None, in_bins or None

    def get_ip_counters(self) -> Optional[Dict[str, AristaIpCounters]]:
        """Collect IP counters via ``show interfaces counters ip | json | no-more``."""
        data = self._run_arista_json(self.CMD_IP_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces counters ip' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaIpCounters] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaIpCounters(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaIpCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_rates_counters(self) -> Optional[Dict[str, AristaRatesCounters]]:
        """Collect rates counters via ``show interfaces counters rates | json | no-more``."""
        data = self._run_arista_json(self.CMD_RATES_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces counters rates' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaRatesCounters] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaRatesCounters(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaRatesCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_pfc_counters(self) -> Optional[Dict[str, AristaPfcCounters]]:
        """Collect PFC counters via ``show priority-flow-control counters``.

        Returns:
            Mapping of port name to :class:`AristaPfcCounters`, or ``None``.
        """
        data = self._run_arista_json(self.CMD_PFC_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show priority-flow-control counters' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaPfcCounters] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaPfcCounters(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaPfcCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_dropped_packet_counters(
        self,
    ) -> Optional[Dict[str, AristaDroppedPacketCounters]]:
        """Collect dropped packet counters via ``show interfaces counters queue``.

        Returns:
            Mapping of port name to :class:`AristaDroppedPacketCounters`,
            or ``None``.
        """
        text = self._run_arista_text(self.CMD_DROPPED_PACKET_COUNTERS)
        if text is None:
            return None
        line_pattern = re.compile(
            r"(?P<port>Et\S+)"
            r"\s+(?P<in_dropped>\d+)"
            r"\s+(?P<out_uc_dropped>\d+)"
            r"\s+(?P<out_mc_dropped>\d+)"
        )
        result: Dict[str, AristaDroppedPacketCounters] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            port_name = self._expand_port_name(match.group("port"))
            try:
                result[port_name] = AristaDroppedPacketCounters(
                    in_dropped_pkts=int(match.group("in_dropped")),
                    out_uc_dropped_pkts=int(match.group("out_uc_dropped")),
                    out_mc_dropped_pkts=int(match.group("out_mc_dropped")),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaDroppedPacketCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_drop_precedence_counters(
        self,
    ) -> Optional[Dict[str, AristaDropPrecedenceCounters]]:
        """Collect drop precedence counters via ``... queue drop-precedence``.

        Returns:
            Mapping of port name to :class:`AristaDropPrecedenceCounters`,
            or ``None``.
        """
        text = self._run_arista_text(self.CMD_DROP_PRECEDENCE_COUNTERS)
        if text is None:
            return None
        line_pattern = re.compile(
            r"(?P<port>Ethernet\S+)" r"\s+(?P<dp0>\d+)" r"\s+(?P<dp1>\d+)" r"\s+(?P<dp2>\d+)"
        )
        result: Dict[str, AristaDropPrecedenceCounters] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            port_name = match.group("port")
            try:
                result[port_name] = AristaDropPrecedenceCounters(
                    dp0_dropped_pkts=int(match.group("dp0")),
                    dp1_dropped_pkts=int(match.group("dp1")),
                    dp2_dropped_pkts=int(match.group("dp2")),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaDropPrecedenceCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_per_queue_counters(
        self,
    ) -> Optional[Dict[str, List[AristaPerQueueCounters]]]:
        """Collect per-queue counters via ``show interfaces counters queue detail``.

        Returns:
            Mapping of port name to a list of :class:`AristaPerQueueCounters`,
            or ``None``.
        """
        text = self._run_arista_text(self.CMD_PER_QUEUE_COUNTERS)
        if text is None:
            return None
        line_pattern = re.compile(
            r"(?P<port>Et\S+)"
            r"\s+(?P<txq>\S+)"
            r"\s+(?P<pkts_counter>\d+)"
            r"\s+(?P<bytes_counter>\d+)"
            r"\s+(?P<pkts_drop>\d+)"
            r"\s+(?P<bytes_drop>\d+)"
        )
        result: Dict[str, List[AristaPerQueueCounters]] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            port_name = self._expand_port_name(match.group("port"))
            try:
                entry = AristaPerQueueCounters(
                    txq=match.group("txq"),
                    pkts_counter=int(match.group("pkts_counter")),
                    bytes_counter=int(match.group("bytes_counter")),
                    pkts_drop=int(match.group("pkts_drop")),
                    bytes_drop=int(match.group("bytes_drop")),
                )
                result.setdefault(port_name, []).append(entry)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaPerQueueCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_pause_frame_counters(
        self,
    ) -> Optional[Dict[str, AristaPauseFrameCounters]]:
        """Collect pause frame counters via ``show interfaces flow-control | json | no-more``."""
        data = self._run_arista_json(self.CMD_PAUSE_FRAME_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceFlowControls", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show interfaces flow-control' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, AristaPauseFrameCounters] = {}
        for port_name, counters in interfaces.items():
            try:
                result[port_name] = AristaPauseFrameCounters(**counters)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build AristaPauseFrameCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_ecn_counters(
        self,
    ) -> Optional[Dict[str, List[AristaEcnCounters]]]:
        """Collect ECN counters via ``show qos interfaces ecn counters queue | json | no-more``.

        Returns:
            A dict mapping port name to a list of per-queue ECN counter entries.
        """
        data = self._run_arista_json(self.CMD_ECN_COUNTERS)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("intfQueueCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Unexpected format for 'show qos interfaces ecn counters queue' output",
                priority=EventPriority.WARNING,
            )
            return None
        result: Dict[str, List[AristaEcnCounters]] = {}
        for port_name, port_data in interfaces.items():
            if not isinstance(port_data, dict):
                continue
            queue_counters = port_data.get("queueCounters", {})
            if not isinstance(queue_counters, dict):
                continue
            entries: List[AristaEcnCounters] = []
            for queue_id, marked_packets in queue_counters.items():
                try:
                    entries.append(
                        AristaEcnCounters(
                            txq=queue_id,
                            marked_packets=str(marked_packets),
                        )
                    )
                except (ValidationError, TypeError) as e:
                    self._log_event(
                        category=EventCategory.SWITCH,
                        description=f"Failed to build AristaEcnCounters for {port_name} queue {queue_id}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
            if entries:
                result[port_name] = entries
        return result or None

    # artifact-only collectors

    def collect_artifact_commands(self) -> None:
        """Run diagnostic commands so their output is captured in ``command_artifacts.json``."""
        for command in self.ARTIFACT_COMMANDS:
            try:
                cmd_ret = self._run_sut_cmd(command)
                if cmd_ret.exit_code != 0:
                    self._log_event(
                        category=EventCategory.SWITCH,
                        description=f"Error running artifact command: `{command}`",
                        data={
                            "command": command,
                            "exit_code": cmd_ret.exit_code,
                            "stderr": cmd_ret.stderr,
                        },
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
                    continue
            except Exception as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Error collecting artifact for command: `{command}`",
                    data={
                        "command": command,
                        "exception": get_exception_traceback(e),
                    },
                    priority=EventPriority.WARNING,
                    console_log=True,
                )

    def _collect_html_view(self, command: str) -> None:
        """Re-run a ``| json`` command without the json tag for readable output."""
        if not self._html_view or "| json" not in command:
            return
        text_command = command.replace(" | json", "")
        try:
            self._run_sut_cmd(text_command)
        except Exception as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description=f"Error running html_view command: `{text_command}`",
                data={
                    "command": text_command,
                    "exception": get_exception_traceback(e),
                },
                priority=EventPriority.WARNING,
                console_log=True,
            )

    def _preflight_check(self) -> Optional[AristaVersion]:
        """Verify the switch is a reachable Arista EOS device.

        Verifies the switch responds to the basic ``show version`` command
        before running the rest of the collector

        On failure this sets ``self.result.status`` to
        :attr:`ExecutionStatus.NOT_RAN` and returns ``None``.

        Returns:
            The collected :class:`AristaVersion` on success, or ``None`` if the
            pre-flight check failed.
        """
        version = self.get_version()
        if version is None:
            self._log_event(
                category=EventCategory.SWITCH,
                description=("ScaleOutAristaCollector pre-flight check failed"),
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return None

        mfg_name = version.mfg_name or ""
        if "arista" not in mfg_name.lower():
            self._log_event(
                category=EventCategory.SWITCH,
                description=("Not Arista switch"),
                data={"mfg_name": mfg_name},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return None

        return version

    # main entry point

    def collect_data(
        self, args: Optional[ScaleOutAristaCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ScaleOutAristaDataModel]]:
        """Run all Arista collectors and assemble the switch data model.

        Args:
            args: Optional :class:`ScaleOutAristaCollectorArgs`.

        Returns:
            Tuple of ``(TaskResult, ScaleOutAristaDataModel | None)``.
        """
        self._html_view = bool(args and args.html_view)

        version = self._preflight_check()
        if version is None:
            return self.result, None

        try:
            lldp_neighbors = self.get_lldp_neighbors()
            system_env = self.get_system_env()

            port_status = self.get_port_status()
            error_counters = self.get_error_counters()
            packet_counters = self.get_packet_counters()
            out_bins, in_bins = self.get_bins_counters()
            ip_counters = self.get_ip_counters()
            rates_counters = self.get_rates_counters()
            pfc_counters = self.get_pfc_counters()
            dropped_packet_counters = self.get_dropped_packet_counters()
            drop_precedence_counters = self.get_drop_precedence_counters()
            per_queue_counters = self.get_per_queue_counters()
            pause_frame_counters = self.get_pause_frame_counters()
            ecn_counters = self.get_ecn_counters()

            self.collect_artifact_commands()
        except Exception as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Error running Arista collector sub commands",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        # Build per-port PortData from all per-port collectors.
        all_port_names: set[str] = set()
        for d in (
            port_status,
            error_counters,
            packet_counters,
            out_bins,
            in_bins,
            ip_counters,
            rates_counters,
            pfc_counters,
            dropped_packet_counters,
            drop_precedence_counters,
            per_queue_counters,
            pause_frame_counters,
            ecn_counters,
        ):
            if d:
                all_port_names.update(d.keys())

        port_data: Optional[Dict[str, PortData]] = None
        if all_port_names:
            port_data = {}
            for name in sorted(all_port_names):
                port_data[name] = PortData(
                    port_status=port_status.get(name) if port_status else None,
                    error_counters=error_counters.get(name) if error_counters else None,
                    packet_counters=packet_counters.get(name) if packet_counters else None,
                    ip_counters=ip_counters.get(name) if ip_counters else None,
                    out_bins_counters=out_bins.get(name) if out_bins else None,
                    in_bins_counters=in_bins.get(name) if in_bins else None,
                    rates_counters=rates_counters.get(name) if rates_counters else None,
                    pfc_counters=pfc_counters.get(name) if pfc_counters else None,
                    dropped_packet_counters=(
                        dropped_packet_counters.get(name) if dropped_packet_counters else None
                    ),
                    dropped_precedence_counters=(
                        drop_precedence_counters.get(name) if drop_precedence_counters else None
                    ),
                    per_queue_counters=per_queue_counters.get(name) if per_queue_counters else None,
                    pause_frame_counters=(
                        pause_frame_counters.get(name) if pause_frame_counters else None
                    ),
                    ecn_counters=ecn_counters.get(name) if ecn_counters else None,
                )

        try:
            arista_data = ScaleOutAristaDataModel(
                version=version,
                lldp_neighbors=lldp_neighbors,
                system_env=system_env,
                port_list=sorted(all_port_names) if all_port_names else None,
                port=port_data,
            )
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Failed to build ScaleOutAristaDataModel",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        self.result.message = "Arista switch data collected"
        return self.result, arista_data
