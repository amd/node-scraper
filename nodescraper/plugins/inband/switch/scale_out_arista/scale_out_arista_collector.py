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
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact, TextFileArtifact
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
    AristaPhyStatus,
    AristaPortStatus,
    AristaRatesCounters,
    AristaSystemEnv,
    AristaVersion,
    PortData,
    ScaleOutAristaDataModel,
)

# Placeholder embedded in every Arista command that supports a per-port
# qualifier.  At command-run time it is replaced with ``ethernet <port>``
# (when a port filter is active) or stripped entirely (when no filter is set).
ETHERNET_PLACEHOLDER = "ethernet_x"

# Matches a single port-spec token like ``1/1``, ``1/1-8`` or ``1/1-8/1``.
_PORT_SPEC_TOKEN_RE = re.compile(
    r"^(\d+(?:/\d+)?)(?:-(\d+(?:/\d+)?))?$",
)


def _normalize_port_spec(ports: Any) -> Optional[List[str]]:
    """Convert a user-supplied port filter into a list of Arista spec strings.

    Each element of the returned list yields a single command invocation.

    Accepted input:
      * None (no filter; commands run once with the placeholder
        stripped).
      * A list of strings -> one spec per element, e.g.
        ["1/1-3/1", "17/1-17/1"] (two command calls).

    """
    if ports is None:
        return None

    if not isinstance(ports, list):
        raise TypeError(f"'ports' must be a list of strings, got {type(ports).__name__}")

    specs: list[str] = []
    for item in ports:
        if not isinstance(item, str):
            raise TypeError(f"Port filter tokens must be strings, got {item!r}")
        cleaned: list[str] = []
        for tok in item.split(","):
            tok = tok.strip()
            if not tok:
                continue
            match = _PORT_SPEC_TOKEN_RE.match(tok)
            if not match:
                raise ValueError(f"Invalid port spec token: {tok!r}")
            start, end = match.group(1), match.group(2)
            cleaned.append(f"{start}-{end}" if end else start)
        if cleaned:
            specs.append(",".join(cleaned))

    return specs or None


class ScaleOutAristaCollector(
    InBandDataCollector[ScaleOutAristaDataModel, ScaleOutAristaCollectorArgs]
):
    """Collect Arista switch data.

    Runs Arista EOS ``show`` commands (JSON and text) and parses their
    output into a :class:`ScaleOutAristaDataModel`.
    """

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX, OSFamily.UNKNOWN}

    DATA_MODEL = ScaleOutAristaDataModel

    # Arista-style port specs set from the ``ports`` arg of
    # :meth:`collect_data`.  When non-None each element triggers one command
    # invocation per ``ethernet_x`` placeholder; the per-call results are
    # merged together.  When None the placeholder is stripped and the command
    # runs once for all ports.
    _port_specs: Optional[List[str]] = None

    # Commands whose output is saved as file artifacts (not parsed into a data model).
    ARTIFACT_COMMANDS: list[str] = [
        "show version",
        "show running-config",
        "show startup-config",
        "show ip interface",
        "show qos profile",
        "show qos profile summary",
        "show qos maps",
        "show qos interfaces",
        "show qos interfaces trust",
        "show priority-flow-control status",
        "show qos interfaces ecn",
        "show lldp",
        # "show priority-flow-control counters watchdog",
        "show platform trident mmu queue status",
    ]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _log_file_artifact(self, filename: str, contents: str) -> None:
        """Append plain-text command output to the result as a file artifact."""
        self.result.artifacts.append(TextFileArtifact(filename=filename, contents=contents))

    def _iter_port_specs(self) -> List[Optional[str]]:
        """Return one entry per command invocation (None when no filter)."""
        return list(self._port_specs) if self._port_specs else [None]

    def _substitute_port_placeholder(self, command: str, spec: Optional[str]) -> str:
        """Replace the ``ethernet_x`` placeholder with ``ethernet <spec>``.

        Args:
            command: Command containing the placeholder.
            spec: Port spec to insert, or ``None`` to strip the placeholder.

        Returns:
            The rendered command string.
        """
        if ETHERNET_PLACEHOLDER not in command:
            return command
        replacement = f"ethernet {spec}" if spec else ""
        result = command.replace(ETHERNET_PLACEHOLDER, replacement)
        # Collapse any double spaces left behind when the placeholder was
        # stripped, and trim trailing whitespace before any pipes.
        return re.sub(r"\s{2,}", " ", result).strip()

    @staticmethod
    def _merge_json(
        accumulated: dict | Optional[list], new: dict | Optional[list]
    ) -> dict | Optional[list]:
        """Merge two JSON results (dicts recursively, lists concatenated).

        Args:
            accumulated: Previously merged result.
            new: New result to merge in.

        Returns:
            The merged JSON value.
        """
        if accumulated is None:
            return new
        if new is None:
            return accumulated
        if isinstance(accumulated, dict) and isinstance(new, dict):
            merged = dict(accumulated)
            for key, value in new.items():
                if key in merged and isinstance(merged[key], (dict, list)):
                    merged[key] = ScaleOutAristaCollector._merge_json(merged[key], value)
                else:
                    merged[key] = value
            return merged
        if isinstance(accumulated, list) and isinstance(new, list):
            return accumulated + new
        return new

    def _run_arista_json(self, command: str) -> dict | Optional[list]:
        """Run an Arista EOS command returning JSON, merging per-spec results.

        Args:
            command: The EOS command (``| json`` is appended automatically).

        Returns:
            Parsed JSON (dict or list), or ``None`` if every call failed.
        """
        specs = self._iter_port_specs() if ETHERNET_PLACEHOLDER in command else [None]
        accumulated: dict | Optional[list] = None
        for spec in specs:
            rendered = self._substitute_port_placeholder(command, spec)
            cmd_ret: CommandArtifact = self._run_sut_cmd(f"{rendered} | json | no-more")
            if cmd_ret.exit_code != 0:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Error running Arista command: `{rendered}`",
                    data={
                        "command": rendered,
                        "exit_code": cmd_ret.exit_code,
                        "stderr": cmd_ret.stderr,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
                continue
            try:
                parsed = json.loads(cmd_ret.stdout)
            except json.JSONDecodeError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Error parsing JSON from Arista command: `{rendered}`",
                    data={
                        "command": rendered,
                        "exception": get_exception_traceback(e),
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
                continue
            accumulated = self._merge_json(accumulated, parsed)
        return accumulated

    def _run_arista_text(self, command: str) -> Optional[str]:
        """Run an Arista EOS command returning text, concatenating per-spec output.

        Args:
            command: The EOS command (``| no-more`` is appended automatically).

        Returns:
            The combined stdout text, or ``None`` if every call failed.
        """
        specs = self._iter_port_specs() if ETHERNET_PLACEHOLDER in command else [None]
        chunks: list[str] = []
        for spec in specs:
            rendered = self._substitute_port_placeholder(command, spec)
            cmd_ret: CommandArtifact = self._run_sut_cmd(f"{rendered} | no-more")
            if cmd_ret.exit_code != 0:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Error running Arista command: `{rendered}`",
                    data={
                        "command": rendered,
                        "exit_code": cmd_ret.exit_code,
                        "stderr": cmd_ret.stderr,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
                continue
            if cmd_ret.stdout:
                chunks.append(cmd_ret.stdout)
        if not chunks:
            return None
        return "\n".join(chunks)

    # ------------------------------------------------------------------
    # sub-collectors
    # ------------------------------------------------------------------

    def get_version(self) -> Optional[AristaVersion]:
        """Collect version information via ``show version | json``."""
        data = self._run_arista_json("show version")
        if not isinstance(data, dict):
            return None
        try:
            return AristaVersion(**data)
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.APPLICATION,
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

    @staticmethod
    def _port_id_from_name(port_name: str) -> Optional[str]:
        """Extract the numeric identifier from an Ethernet port name.

        Args:
            port_name: Full port name (e.g. ``"Ethernet1/1"``).

        Returns:
            The portion after ``Ethernet`` (e.g. ``"1/1"``), or ``None``.
        """
        match = re.match(r"Ethernet(\S+)", port_name)
        return match.group(1) if match else None

    def get_port_status(self, port_names: list[str]) -> Optional[Dict[str, AristaPortStatus]]:
        """Collect per-port status via ``show interfaces ethernet <id> status``.

        Args:
            port_names: Port names to query (e.g. ``["Ethernet1/1"]``).

        Returns:
            Mapping of port name to :class:`AristaPortStatus`, or ``None``.
        """
        result: Dict[str, AristaPortStatus] = {}
        for port_name in port_names:
            port_id = self._port_id_from_name(port_name)
            if port_id is None:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Could not extract port id from: {port_name}",
                    priority=EventPriority.WARNING,
                )
                continue
            data = self._run_arista_json(f"show interfaces Ethernet {port_id} status")
            if not isinstance(data, dict):
                continue
            interfaces = data.get("interfaceStatuses", data)
            if not isinstance(interfaces, dict):
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Unexpected format for port status of {port_name}",
                    priority=EventPriority.WARNING,
                )
                continue
            # The response is keyed by port name; grab the matching entry.
            port_data = interfaces.get(port_name)
            if port_data is None and interfaces:
                # Fallback: take the first (and likely only) entry.
                port_data = next(iter(interfaces.values()))
            if port_data is None:
                continue
            try:
                result[port_name] = AristaPortStatus(**port_data)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build AristaPortStatus for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_phy_status(self) -> Optional[Dict[str, AristaPhyStatus]]:
        """Collect PHY status via ``show interfaces phy | json``.

        Returns:
            Mapping of port name to :class:`AristaPhyStatus`, or ``None``.
        """
        data = self._run_arista_json("show interfaces ethernet_x phy")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfacePhyStatuses", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Unexpected format for 'show interfaces phy' output",
                priority=EventPriority.WARNING,
            )
            return None
        return self.parse_phy_status(interfaces)

    @staticmethod
    def parse_phy_status(
        interfaces: Dict[str, dict],
    ) -> Optional[Dict[str, AristaPhyStatus]]:
        """Parse the JSON output of ``show interfaces phy`` into models.

        Args:
            interfaces: The ``interfacePhyStatuses`` dict from the output.

        Returns:
            Mapping of port name to :class:`AristaPhyStatus`, or ``None``.
        """
        # Pattern to match the fixed-width text row embedded in each entry.
        #   Port           PHY state      StateChanges ResetCount PMA/PMD PCS   XAUI
        line_pattern = re.compile(
            r"(?P<port>Ethernet\S+)"  # Port name (starts with Ethernet)
            r"\s+"
            r"(?P<phy_state>\S+)"  # PHY state (e.g. linkUp, linkDown)
            r"\s+"
            r"(?P<state_changes>\d+)"  # State Changes
            r"\s+"
            r"(?P<reset_count>\d+|-)"  # Reset Count (integer or '-')
            r"\s+"
            r"(?P<pma_pmd>\S+)"  # PMA/PMD flags
            r"\s+"
            r"(?P<pcs>\S+)"  # PCS flags
            r"\s+"
            r"(?P<xaui>\S+)"  # XAUI flags
        )

        result: Dict[str, AristaPhyStatus] = {}
        for port_name, entry in interfaces.items():
            if not isinstance(entry, dict):
                continue
            text = entry.get("text", "")
            match = line_pattern.search(text)
            if not match:
                continue

            pma_pmd = match.group("pma_pmd")
            pcs = match.group("pcs")
            xaui = match.group("xaui")
            reset_count_raw = match.group("reset_count")

            # Decode PMA/PMD flags (3 chars: [U/D][R/.][T/.])
            link_up = pma_pmd[0] == "U" if len(pma_pmd) >= 1 else None
            rx_fault = pma_pmd[1] == "R" if len(pma_pmd) >= 2 else None
            tx_fault = pma_pmd[2] == "T" if len(pma_pmd) >= 3 else None

            # Decode PCS flags (up to 5 chars: [U/D][B/.][.][.][L/.])
            high_ber = pcs[1] == "B" if len(pcs) >= 2 else None
            no_block_lock = pcs[4] == "L" if len(pcs) >= 5 else None

            # Decode XAUI flags
            no_xaui_lane_alignment = "A" in xaui if xaui != "-" else None
            no_xaui_lane_sync: Optional[List[int]] = None
            if xaui != "-":
                lanes = [int(ch) for ch in xaui if ch.isdigit()]
                no_xaui_lane_sync = lanes if lanes else None

            result[port_name] = AristaPhyStatus(
                phy_state=match.group("phy_state"),
                state_changes=int(match.group("state_changes")),
                reset_count=int(reset_count_raw) if reset_count_raw != "-" else None,
                pma_pmd=pma_pmd,
                pcs=pcs,
                xaui=xaui,
                link_up=link_up,
                rx_fault=rx_fault,
                tx_fault=tx_fault,
                high_ber=high_ber,
                no_block_lock=no_block_lock,
                no_xaui_lane_alignment=no_xaui_lane_alignment,
                no_xaui_lane_sync=no_xaui_lane_sync,
            )

        return result or None

    def get_lldp_neighbors(self) -> Optional[AristaNeighbors]:
        """Collect LLDP neighbor info via ``show lldp neighbors | json | no-more``."""
        data = self._run_arista_json("show lldp neighbors")
        if not isinstance(data, dict):
            return None
        try:
            return AristaNeighbors(**data)
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AristaNeighbors model",
                data=get_exception_details(e),
                priority=EventPriority.WARNING,
            )
            return None

    def get_system_env(self) -> Optional[AristaSystemEnv]:
        """Collect system environment via ``show system environment cooling | json | no-more``."""
        data = self._run_arista_json("show system environment cooling")
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
                category=EventCategory.APPLICATION,
                description="Failed to build AristaSystemEnv model",
                data=get_exception_details(e),
                priority=EventPriority.WARNING,
            )
            return None

    def get_error_counters(self) -> Optional[Dict[str, AristaCountersErrors]]:
        """Collect error counters via ``show interfaces counters errors | json | no-more``."""
        data = self._run_arista_json("show interfaces ethernet_x counters errors")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceErrorCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build AristaCountersErrors for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_packet_counters(self) -> Optional[Dict[str, AristaPacketCounters]]:
        """Collect packet counters via ``show interfaces counters | json | no-more``."""
        data = self._run_arista_json("show interfaces ethernet_x counters")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
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
        data = self._run_arista_json("show interfaces ethernet_x counters bins")
        if not isinstance(data, dict):
            return None, None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                        category=EventCategory.APPLICATION,
                        description=f"Failed to build out AristaBinsCounters for {port_name}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
            if in_data:
                try:
                    in_bins[port_name] = AristaBinsCounters(**in_data)
                except (ValidationError, TypeError) as e:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Failed to build in AristaBinsCounters for {port_name}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
        return out_bins or None, in_bins or None

    def get_ip_counters(self) -> Optional[Dict[str, AristaIpCounters]]:
        """Collect IP counters via ``show interfaces counters ip | json | no-more``."""
        data = self._run_arista_json("show interfaces ethernet_x counters ip")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build AristaIpCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_rates_counters(self) -> Optional[Dict[str, AristaRatesCounters]]:
        """Collect rates counters via ``show interfaces counters rates | json | no-more``."""
        data = self._run_arista_json("show interfaces ethernet_x counters rates")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaces", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
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
        if self._port_specs:
            command = "show priority-flow-control interfaces ethernet_x counters"
        else:
            command = "show priority-flow-control counters"
        data = self._run_arista_json(command)
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
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
        text = self._run_arista_text("show interfaces ethernet_x counters queue")
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
                    category=EventCategory.APPLICATION,
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
        text = self._run_arista_text("show interfaces ethernet_x counters queue drop-precedence")
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
                    category=EventCategory.APPLICATION,
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
        text = self._run_arista_text("show interfaces ethernet_x counters queue detail")
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
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build AristaPerQueueCounters for {port_name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_pause_frame_counters(
        self,
    ) -> Optional[Dict[str, AristaPauseFrameCounters]]:
        """Collect pause frame counters via ``show interfaces flow-control | json | no-more``."""
        data = self._run_arista_json("show interfaces ethernet_x flow-control")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("interfaceFlowControls", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                    category=EventCategory.APPLICATION,
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
        data = self._run_arista_json("show qos interfaces ethernet_x ecn counters queue")
        if not isinstance(data, dict):
            return None
        interfaces = data.get("intfQueueCounters", data)
        if not isinstance(interfaces, dict):
            self._log_event(
                category=EventCategory.APPLICATION,
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
                        category=EventCategory.APPLICATION,
                        description=f"Failed to build AristaEcnCounters for {port_name} queue {queue_id}",
                        data=get_exception_details(e),
                        priority=EventPriority.WARNING,
                    )
            if entries:
                result[port_name] = entries
        return result or None

    # ------------------------------------------------------------------
    # artifact-only collectors
    # ------------------------------------------------------------------

    @staticmethod
    def _command_to_filename(command: str) -> str:
        """Convert a command string to a ``.log`` filename.

        Args:
            command: The command string.

        Returns:
            Filename with spaces/hyphens replaced by underscores.
        """
        return command.replace(" ", "_").replace("-", "_") + ".log"

    def collect_artifact_commands(self) -> None:
        """Run diagnostic commands and store their output as file artifacts.

        Failures are logged but do **not** cause the overall collection to fail.
        """
        for command in self.ARTIFACT_COMMANDS:
            specs = self._iter_port_specs() if ETHERNET_PLACEHOLDER in command else [None]
            chunks: list[str] = []
            for spec in specs:
                substituted = self._substitute_port_placeholder(command, spec)
                full_cmd = f"{substituted} | no-more"
                try:
                    cmd_ret = self._run_sut_cmd(full_cmd)
                    if cmd_ret.exit_code != 0:
                        self._log_event(
                            category=EventCategory.APPLICATION,
                            description=f"Error running artifact command: `{command}`",
                            data={
                                "command": full_cmd,
                                "exit_code": cmd_ret.exit_code,
                                "stderr": cmd_ret.stderr,
                            },
                            priority=EventPriority.ERROR,
                            console_log=True,
                        )
                        continue
                    if cmd_ret.stdout:
                        chunks.append(cmd_ret.stdout)
                except Exception as e:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Error collecting artifact for command: `{command}`",
                        data={
                            "command": command,
                            "exception": get_exception_traceback(e),
                        },
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
            if chunks:
                try:
                    self._log_file_artifact(self._command_to_filename(command), "\n".join(chunks))
                except Exception as e:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Error saving artifact for command: `{command}`",
                        data={
                            "command": command,
                            "exception": get_exception_traceback(e),
                        },
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------

    def collect_data(
        self, args: Optional[ScaleOutAristaCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ScaleOutAristaDataModel]]:
        """Run all Arista collectors and assemble the switch data model.

        Args:
            args: Optional :class:`ScaleOutAristaCollectorArgs`; its ``ports``
                attribute restricts collection, defaulting to all ports.

        Returns:
            Tuple of ``(TaskResult, ScaleOutAristaDataModel | None)``.
        """
        ports = args.collection_ports if args else None
        try:
            self._port_specs = _normalize_port_spec(ports)
        except (TypeError, ValueError) as exc:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Invalid 'ports' arg for ScaleOutAristaCollector: {exc}",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        # Pre-flight check: verify the switch responds to the basic `show version`
        # command before running the rest of the collector, and that the
        # reported ``mfgName`` identifies the device as an Arista switch.  If
        # either check fails, the device is unreachable, not an Arista EOS
        # switch, or otherwise incompatible -- treat like an unsupported OS
        # and bail out early.
        version = self.get_version()
        if version is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=("ScaleOutAristaCollector pre-flight check failed"),
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        mfg_name = version.mfg_name or ""
        if "arista" not in mfg_name.lower():
            self._log_event(
                category=EventCategory.APPLICATION,
                description=("Not Arista switch"),
                data={"mfg_name": mfg_name},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        try:
            lldp_neighbors = self.get_lldp_neighbors()
            system_env = self.get_system_env()

            phy_status = self.get_phy_status()
            port_names = list(phy_status.keys()) if phy_status else []
            port_status = self.get_port_status(port_names) if port_names else None
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
                category=EventCategory.APPLICATION,
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
            phy_status,
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
                    phy_status=phy_status.get(name) if phy_status else None,
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
                category=EventCategory.APPLICATION,
                description="Failed to build ScaleOutAristaDataModel",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        self.result.message = "Arista switch data collected"
        return self.result, arista_data
