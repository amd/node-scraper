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

import re
from typing import Dict, List, Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact, TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_details, get_exception_traceback

from .collector_args import ScaleOutDellCollectorArgs
from .scaleoutdelldata import (
    DellArpEntry,
    DellFecStatus,
    DellInterfaceCounters,
    DellInterfaceDetailCounters,
    DellInterfaceStatus,
    DellPfcStatistics,
    DellPfcWatchdogQueueStats,
    DellPortData,
    DellQueueCounter,
    DellRouteEntry,
    ScaleOutDellDataModel,
)

# Substrings used to recognize a Dell SONiC switch from ``show version`` output.
# Matched case-insensitively.
DELL_VERSION_MARKERS: tuple[str, ...] = ("dell", "sonic")


class ScaleOutDellCollector(InBandDataCollector[ScaleOutDellDataModel, ScaleOutDellCollectorArgs]):
    """Collect Dell SONiC switch data.

    Runs Dell SONiC CLI ``show`` commands over SSH and parses their text
    output into a :class:`ScaleOutDellDataModel`.
    """

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX, OSFamily.UNKNOWN}

    DATA_MODEL = ScaleOutDellDataModel

    # Commands whose output is saved as file artifacts (not parsed into the data model).
    ARTIFACT_COMMANDS: list[str] = [
        "show clock",
        "show version",
        "show platform syseeprom",
        "show platform firmware detail",
        "show running-configuration",
        "show interface transceiver",
        "show interface transceiver summary",
        "show ip interfaces",
        "show qos map dscp-tc",
        "show qos map tc-queue",
        "show qos map tc-pg",
        "show qos map tc-dscp",
        "show qos map tc-dot1p",
        "show qos map pfc-priority-queue",
        "show qos map pfc-priority-pg",
        "show qos map dot1p-tc",
        "show qos scheduler-policy",
        "show qos wred-policy",
        "show qos interface Eth all",
        "show qos interface Eth all queue all",
        "show priority-flow-control watchdog",
        "show buffer profile",
        "show buffer pool",
        "show interface transceiver dom",
        "show lldp table",
        "show lldp neighbor",
        "show interface Eth",
        "show interface phy counters",
        "show interface counters rate",
        "show queue watermark unicast",
        "show queue watermark multicast",
        "show queue persistent-watermark unicast",
        "show queue persistent-watermark multicast",
        "show platform environment",
        "show event details",
        "show alarm",
        "show interface fec status",  # temporarily added as artifact
    ]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _log_file_artifact(self, filename: str, contents: str) -> None:
        """Append plain-text command output to the result as a file artifact."""
        self.result.artifacts.append(TextFileArtifact(filename=filename, contents=contents))

    @staticmethod
    def _is_dell_output(text: str) -> bool:
        lowered = text.lower()
        return all(marker in lowered for marker in DELL_VERSION_MARKERS)

    @staticmethod
    def _wrap_sonic_cli(command: str) -> str:
        """Wrap a command to run inside the Dell SONiC CLI shell.

        Args:
            command: The CLI command to wrap.

        Returns:
            The command as ``sonic-cli -c "<command>"``.
        """
        return f'sonic-cli -c "{command}"'

    def _run_dell_command(self, command: str) -> Optional[str]:
        """Run a Dell SONiC CLI command via ``sonic-cli -c`` with paging suppressed.

        Args:
            command: The CLI command to run.

        Returns:
            The command stdout, or ``None`` on error.
        """
        inner = command if command.strip() == "show version" else f"{command} | no-more"
        full_cmd = self._wrap_sonic_cli(inner)
        cmd_ret: CommandArtifact = self._run_sut_cmd(full_cmd)
        if cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Error running Dell command: `{full_cmd}`",
                data={
                    "command": full_cmd,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        return cmd_ret.stdout or ""

    # ------------------------------------------------------------------
    # sub-collectors
    # ------------------------------------------------------------------

    def get_interface_status(self) -> Optional[Dict[str, DellInterfaceStatus]]:
        """Parse ``show interface status`` into per-port status models.

        Returns:
            Mapping of port name to :class:`DellInterfaceStatus`, or ``None``.
        """
        text = self._run_dell_command("show interface status")
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<name>Eth\S+)"
            r"\s+(?P<description>\S+)"
            r"\s+(?P<oper>\S+)"
            r"\s+(?P<reason>\S+)"
            r"\s+(?P<auto_neg>\S+)"
            r"\s+(?P<speed>\d+)"
            r"\s+(?P<mtu>\d+)"
            r"\s+(?P<alt>\S+)"
        )
        result: Dict[str, DellInterfaceStatus] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("name")
            try:
                result[name] = DellInterfaceStatus(
                    name=name,
                    description=match.group("description"),
                    oper=match.group("oper"),
                    reason=match.group("reason"),
                    auto_neg=match.group("auto_neg"),
                    speed=int(match.group("speed")),
                    mtu=int(match.group("mtu")),
                    alternate_name=match.group("alt"),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellInterfaceStatus for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_interface_counters(self) -> Optional[Dict[str, DellInterfaceCounters]]:
        """Parse ``show interface counters`` into per-port counter models.

        Returns:
            Mapping of port name to :class:`DellInterfaceCounters`, or ``None``.
        """
        text = self._run_dell_command("show interface counters")
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<name>Eth\S+)"
            r"\s+(?P<state>\S+)"
            r"\s+(?P<rx_ok>\d+)"
            r"\s+(?P<rx_err>\d+)"
            r"\s+(?P<rx_drp>\d+)"
            r"\s+(?P<rx_oversize>\d+)"
            r"\s+(?P<tx_ok>\d+)"
            r"\s+(?P<tx_err>\d+)"
            r"\s+(?P<tx_drp>\d+)"
            r"\s+(?P<tx_oversize>\d+)"
        )
        result: Dict[str, DellInterfaceCounters] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("name")
            try:
                result[name] = DellInterfaceCounters(
                    state=match.group("state"),
                    rx_ok=int(match.group("rx_ok")),
                    rx_err=int(match.group("rx_err")),
                    rx_drp=int(match.group("rx_drp")),
                    rx_oversize=int(match.group("rx_oversize")),
                    tx_ok=int(match.group("tx_ok")),
                    tx_err=int(match.group("tx_err")),
                    tx_drp=int(match.group("tx_drp")),
                    tx_oversize=int(match.group("tx_oversize")),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellInterfaceCounters for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    @staticmethod
    def _label_to_field(label: str) -> str:
        """Convert an ``Interface Detail Counters`` label to a snake-case field name."""
        return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

    def get_detail_counters(
        self,
        port_names: List[str],
    ) -> Optional[Dict[str, DellInterfaceDetailCounters]]:
        """Parse ``show interface counters <port>`` for each given port.

        Args:
            port_names: Ports to query.

        Returns:
            Mapping of port name to :class:`DellInterfaceDetailCounters`, or ``None``.
        """
        if not port_names:
            return None
        result: Dict[str, DellInterfaceDetailCounters] = {}
        for port_name in port_names:
            text = self._run_dell_command(f"show interface counters {port_name}")
            if text is None:
                continue
            parsed = self._parse_detail_counters_block(text)
            if parsed is None:
                continue
            result[port_name] = parsed
        return result or None

    @classmethod
    def _parse_detail_counters_block(cls, text: str) -> Optional[DellInterfaceDetailCounters]:
        """Parse one port's ``<label>  <value>`` detail-counter rows.

        Args:
            text: Raw command output for a single port.

        Returns:
            A :class:`DellInterfaceDetailCounters`, or ``None`` if empty.
        """
        kwargs: Dict[str, str] = {}
        line_pattern = re.compile(r"^(?P<label>.+?)\s{2,}(?P<value>\S+)\s*$")
        for line in text.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            match = line_pattern.match(stripped)
            if not match:
                continue
            field = cls._label_to_field(match.group("label").strip())
            if field not in DellInterfaceDetailCounters.model_fields:
                continue
            kwargs[field] = match.group("value").strip()
        if not kwargs:
            return None
        try:
            return DellInterfaceDetailCounters.model_validate(kwargs)
        except (ValidationError, TypeError):
            return None

    def get_fec_status(self) -> Optional[Dict[str, DellFecStatus]]:
        """Parse ``show interface fec status`` into per-port FEC models.

        Returns:
            Mapping of port name to :class:`DellFecStatus`, or ``None``.
        """
        text = self._run_dell_command("show interface fec status")
        if text is None:
            return None
        result: Dict[str, DellFecStatus] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or not stripped.startswith("Eth"):
                continue
            tokens = stripped.split()
            if len(tokens) < 4:
                continue
            name = tokens[0]
            if_state = tokens[-1]
            admin = tokens[-2]
            oper = tokens[-3]
            type_str = " ".join(tokens[1:-3]) if len(tokens) > 4 else None
            try:
                result[name] = DellFecStatus(
                    type=type_str,
                    oper=oper,
                    admin=admin,
                    if_state=if_state,
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellFecStatus for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_ip_arp(self) -> Optional[List[DellArpEntry]]:
        """Parse ``show ip arp`` into ARP table entries.

        Returns:
            List of :class:`DellArpEntry`, or ``None``.
        """
        text = self._run_dell_command("show ip arp")
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<address>\d+\.\d+\.\d+\.\d+)"
            r"\s+(?P<hw>[0-9a-fA-F:]{17})"
            r"\s+(?P<iface>\S+)"
            r"\s+(?P<egress>\S+)"
            r"\s+(?P<type>\S+)"
            r"\s+(?P<action>\S+)"
        )
        result: List[DellArpEntry] = []
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            try:
                result.append(
                    DellArpEntry(
                        address=match.group("address"),
                        hardware_address=match.group("hw"),
                        interface=match.group("iface"),
                        egress_interface=match.group("egress"),
                        type=match.group("type"),
                        action=match.group("action"),
                    )
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build DellArpEntry",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_ip_route(self) -> Optional[List[DellRouteEntry]]:
        """Parse ``show ip route`` into route table entries.

        Returns:
            List of :class:`DellRouteEntry`, or ``None``.
        """
        text = self._run_dell_command("show ip route")
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<code>\S+)"
            r"\s+(?P<dest>\d[^\s]*)"
            r"\s+(?P<gateway>via\s+\S+|Direct)"
            r"\s+(?P<iface>\S+)"
            r"\s+(?P<dm>\d+/\d+)"
            r"\s+(?P<last>.+?\sago)\s*$"
        )
        result: List[DellRouteEntry] = []
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            try:
                result.append(
                    DellRouteEntry(
                        code=match.group("code"),
                        destination=match.group("dest"),
                        gateway=match.group("gateway"),
                        interface=match.group("iface"),
                        distance_metric=match.group("dm"),
                        last_update=match.group("last").strip(),
                    )
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build DellRouteEntry",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_pfc_statistics(
        self,
    ) -> tuple[Optional[Dict[str, DellPfcStatistics]], Optional[Dict[str, DellPfcStatistics]]]:
        """Parse PFC RX/TX statistics from ``priority-flow-control statistics``.

        Returns:
            Tuple of ``(rx_by_port, tx_by_port)`` dicts, each value or ``None``.
        """
        cmd = "show qos interface Ethall priority-flow-control statistics"
        text = self._run_dell_command(cmd)
        if text is None:
            return None, None

        rx: Dict[str, DellPfcStatistics] = {}
        tx: Dict[str, DellPfcStatistics] = {}
        current = rx  # default to RX until we see the transmitted header
        line_pattern = re.compile(
            r"^(?P<name>Eth\S+)" + "".join(rf"\s+(?P<pfc{i}>\d+)" for i in range(8))
        )
        for line in text.splitlines():
            stripped = line.strip()
            low = stripped.lower()
            if "flow control frames received" in low:
                current = rx
                continue
            if "flow control frames transmitted" in low:
                current = tx
                continue
            match = line_pattern.match(stripped)
            if not match:
                continue
            name = match.group("name")
            try:
                current[name] = DellPfcStatistics(
                    **{f"pfc{i}": int(match.group(f"pfc{i}")) for i in range(8)}
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellPfcStatistics for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return rx or None, tx or None

    def get_pfc_watchdog_statistics(
        self,
    ) -> Optional[Dict[str, List[DellPfcWatchdogQueueStats]]]:
        """Parse per-queue PFC watchdog statistics for each port.

        Returns:
            Mapping of port name to a list of
            :class:`DellPfcWatchdogQueueStats`, or ``None``.
        """
        cmd = "show qos interface Ethall queue all priority-flow-control watchdog-statistics"

        text = self._run_dell_command(cmd)
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<name>Eth\S+)"
            r"\s+(?P<queue>\d+)"
            r"\s+(?P<status>\S+)"
            r"\s+(?P<storms_det>\d+)"
            r"\s+(?P<storms_res>\d+)"
            r"\s+(?P<tx_ok>\d+)"
            r"\s+(?P<tx_drop>\d+)"
            r"\s+(?P<rx_ok>\d+)"
            r"\s+(?P<rx_drop>\d+)"
            r"\s+(?P<tx_last_ok>\d+)"
            r"\s+(?P<tx_last_drop>\d+)"
            r"\s+(?P<rx_last_ok>\d+)"
            r"\s+(?P<rx_last_drop>\d+)"
        )
        result: Dict[str, List[DellPfcWatchdogQueueStats]] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("name")
            try:
                entry = DellPfcWatchdogQueueStats(
                    queue=int(match.group("queue")),
                    status=match.group("status"),
                    storms_detected=int(match.group("storms_det")),
                    storms_restored=int(match.group("storms_res")),
                    transmitted_ok=int(match.group("tx_ok")),
                    transmitted_drop=int(match.group("tx_drop")),
                    received_ok=int(match.group("rx_ok")),
                    received_drop=int(match.group("rx_drop")),
                    tx_last_ok=int(match.group("tx_last_ok")),
                    tx_last_drop=int(match.group("tx_last_drop")),
                    rx_last_ok=int(match.group("rx_last_ok")),
                    rx_last_drop=int(match.group("rx_last_drop")),
                )
                result.setdefault(name, []).append(entry)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellPfcWatchdogQueueStats for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_queue_counters(self) -> Optional[Dict[str, List[DellQueueCounter]]]:
        """Parse ``show queue counters`` (``Eth*`` rows only) per port.

        Returns:
            Mapping of port name to a list of :class:`DellQueueCounter`,
            or ``None``.
        """
        text = self._run_dell_command("show queue counters")
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<port>Eth\S+)"
            r"\s+(?P<txq>\S+)"
            r"\s+(?P<pkts>\d+)"
            r"\s+(?P<bytes>\d+)"
            r"\s+(?P<pps>\S+)"
            r"\s+(?P<bps>\S+)"
            r"\s+(?P<bits_ps>\S+)"
            r"\s+(?P<drop_pkts>\d+)"
            r"\s+(?P<drop_bytes>\d+)"
        )
        result: Dict[str, List[DellQueueCounter]] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("port")
            try:
                entry = DellQueueCounter(
                    txq=match.group("txq"),
                    counter_pkts=int(match.group("pkts")),
                    counter_bytes=int(match.group("bytes")),
                    rate_pps=match.group("pps"),
                    rate_bps=match.group("bps"),
                    rate_bits_ps=match.group("bits_ps"),
                    drop_pkts=int(match.group("drop_pkts")),
                    drop_bytes=int(match.group("drop_bytes")),
                )
                result.setdefault(name, []).append(entry)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build DellQueueCounter for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    # ------------------------------------------------------------------
    # artifact-only collectors
    # ------------------------------------------------------------------

    @staticmethod
    def _command_to_filename(command: str) -> str:
        """Convert a command string to a log filename."""
        return command.replace(" ", "_").replace("-", "_") + ".log"

    def collect_artifact_commands(self) -> None:
        """Run diagnostic commands and store their output as file artifacts.

        Failures are logged but do **not** cause the overall collection to fail.
        """
        for command in self.ARTIFACT_COMMANDS:
            inner = command if command.strip() == "show version" else f"{command} | no-more"
            full_cmd = self._wrap_sonic_cli(inner)
            try:
                cmd_ret = self._run_sut_cmd(full_cmd)
                if cmd_ret.exit_code != 0:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Error running artifact command: `{full_cmd}`",
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
                    self._log_file_artifact(self._command_to_filename(command), cmd_ret.stdout)
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

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------

    def collect_data(
        self, args: Optional[ScaleOutDellCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ScaleOutDellDataModel]]:
        """Run all Dell collectors and assemble the switch data model.

        Args:
            args: Optional :class:`ScaleOutDellCollectorArgs`; its ``ports``
                attribute restricts per-port detail collection, defaulting to
                every port from ``show interface status``.

        Returns:
            Tuple of ``(TaskResult, ScaleOutDellDataModel | None)``.
        """
        # Pre-flight: ensure the device responds and identifies as Dell SONiC.
        # ``_run_dell_command`` wraps every command in ``sonic-cli -c "..."``,
        # so there is no separate "enter the shell" step -- each SSH exec is
        # self-contained.
        version_text = self._run_dell_command("show version")
        if version_text is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="ScaleOutDellCollector pre-flight check failed",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        if not self._is_dell_output(version_text):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Not a Dell SONiC switch",
                data={"raw_output": version_text},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        try:
            interface_status = self.get_interface_status()
            interface_counters = self.get_interface_counters()
            fec_status = self.get_fec_status()
            ip_arp = self.get_ip_arp()
            ip_route = self.get_ip_route()
            pfc_rx, pfc_tx = self.get_pfc_statistics()
            pfc_watchdog = self.get_pfc_watchdog_statistics()
            queue_counters = self.get_queue_counters()

            # Determine the port list before issuing per-port commands.
            ports_arg = args.collection_ports if args else None
            if ports_arg is not None:
                if not isinstance(ports_arg, list) or not all(
                    isinstance(p, str) for p in ports_arg
                ):
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Invalid 'ports' arg for ScaleOutDellCollector",
                        data={"ports": ports_arg},
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
                    self.result.status = ExecutionStatus.EXECUTION_FAILURE
                    return self.result, None
                detail_port_names = [p if p.startswith("Eth") else f"Eth{p}" for p in ports_arg]
            elif interface_status:
                detail_port_names = list(interface_status.keys())
            else:
                detail_port_names = []

            detail_counters = self.get_detail_counters(detail_port_names)

            self.collect_artifact_commands()
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running Dell collector sub commands",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        # The canonical port list comes from ``show interface status`` so
        # that names are in ``Eth1/x/y`` form (not the SONiC ``EthernetN``
        # alternate names returned by some other commands).
        all_port_names: set[str] = set(interface_status.keys()) if interface_status else set()

        port_data: Optional[Dict[str, DellPortData]] = None
        if all_port_names:
            port_data = {}
            for name in sorted(all_port_names):
                port_data[name] = DellPortData(
                    interface_status=interface_status.get(name) if interface_status else None,
                    interface_counters=(
                        interface_counters.get(name) if interface_counters else None
                    ),
                    detail_counters=detail_counters.get(name) if detail_counters else None,
                    fec_status=fec_status.get(name) if fec_status else None,
                    pfc_rx_statistics=pfc_rx.get(name) if pfc_rx else None,
                    pfc_tx_statistics=pfc_tx.get(name) if pfc_tx else None,
                    pfc_watchdog_statistics=(pfc_watchdog.get(name) if pfc_watchdog else None),
                    queue_counters=queue_counters.get(name) if queue_counters else None,
                )

        try:
            dell_data = ScaleOutDellDataModel(
                ip_arp=ip_arp,
                ip_route=ip_route,
                port_list=sorted(all_port_names) if all_port_names else None,
                port=port_data,
            )
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build ScaleOutDellDataModel",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        self.result.message = "Dell switch data collected"
        return self.result, dell_data
