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
from typing import Dict, List, Optional, TypedDict

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_details, get_exception_traceback

from .collector_args import ScaleUpSonicCollectorArgs
from .scaleupsonicdata import (
    ScaleUpSonicDataModel,
    SonicFecStatus,
    SonicInterfaceCounters,
    SonicInterfaceStatus,
    SonicPortData,
    SonicQueueCounter,
)


class _ParsedInterfaceStatusLine(TypedDict):
    name: str
    lanes: str
    speed: str
    mtu: Optional[int]
    fec: str
    alias: str
    vlan: str
    oper: str
    admin: str
    type: str
    asym_pfc: str


# Counter columns are comma grouped and may be reported as ``N/A``
_COUNT = r"[\d,]+|N/A"


class ScaleUpSonicCollector(InBandDataCollector[ScaleUpSonicDataModel, ScaleUpSonicCollectorArgs]):
    """Collect scale up SONiC switch data.

    Runs SONiC ``show`` commands over SSH and parses their text output into a
    :class:`ScaleUpSonicDataModel`. Unlike the Dell collector, commands are
    issued directly and are **not** wrapped in ``sonic-cli -c``.
    """

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.SONIC, OSFamily.LINUX, OSFamily.UNKNOWN}

    DATA_MODEL = ScaleUpSonicDataModel

    CMD_VERSION = "show version"
    CMD_INTERFACE_STATUS = "show interface status"
    CMD_INTERFACE_COUNTERS = "show interface counters"
    CMD_FEC_STATUS = "show interface fec status"
    CMD_QUEUE_COUNTERS = "show queue counters"

    # Commands run for diagnostics, not parsed into a data model.
    CMD_CLOCK = "show clock"
    CMD_PLATFORM_SYSEEPROM = "show platform syseeprom"
    CMD_PLATFORM_FIRMWARE_DETAIL = "show platform firmware version"
    CMD_IP_INTERFACES = "show ip interfaces"
    CMD_LLDP_TABLE = "show lldp table"
    CMD_LLDP_NEIGHBOR = "show lldp neighbors"
    CMD_QUEUE_WATERMARK_UNICAST = "show queue watermark unicast"
    CMD_QUEUE_WATERMARK_MULTICAST = "show queue watermark multicast"
    CMD_QUEUE_PERSISTENT_WATERMARK_UNICAST = "show queue persistent-watermark unicast"
    CMD_QUEUE_PERSISTENT_WATERMARK_MULTICAST = "show queue persistent-watermark multicast"
    CMD_PLATFORM_ENVIRONMENT = "show platform summary"

    _INTERFACE_STATUS_LINE_RE = re.compile(
        r"^"
        r"(?P<name>Ethernet\S*)"
        r"\s+(?P<lanes>\S+)"
        r"\s+(?P<speed>\S+)"
        r"\s+(?P<mtu>\S+)"
        r"\s+(?P<fec>\S+)"
        r"\s+(?P<alias>\S+)"
        r"\s+(?P<vlan>\S+)"
        r"\s+(?P<oper>\S+)"
        r"\s+(?P<admin>\S+)"
        r"\s+(?P<type>\S+)"
        r"\s+(?P<asym_pfc>\S+)"
        r"\s*$"
    )

    # Aggregate of the diagnostic CMD_* commands above
    ARTIFACT_COMMANDS: list[str] = [
        CMD_CLOCK,
        CMD_PLATFORM_SYSEEPROM,
        CMD_PLATFORM_FIRMWARE_DETAIL,
        CMD_IP_INTERFACES,
        CMD_LLDP_TABLE,
        CMD_LLDP_NEIGHBOR,
        CMD_QUEUE_WATERMARK_UNICAST,
        CMD_QUEUE_WATERMARK_MULTICAST,
        CMD_QUEUE_PERSISTENT_WATERMARK_UNICAST,
        CMD_QUEUE_PERSISTENT_WATERMARK_MULTICAST,
        CMD_PLATFORM_ENVIRONMENT,
    ]

    # helpers
    @staticmethod
    def _is_sonic_output(text: str) -> bool:
        return "sonic" in text.lower()

    @staticmethod
    def _to_int(value: str) -> Optional[int]:
        """Convert a comma grouped counter value to an int, or ``None`` if not numeric."""
        try:
            return int(value.replace(",", ""))
        except ValueError:
            return None

    def _run_sonic_command(self, command: str) -> Optional[str]:
        """Run a SONiC CLI command directly, without a ``sonic-cli -c`` wrapper.

        Args:
            command: The full CLI command to run.

        Returns:
            The command stdout, or ``None`` on error.
        """
        cmd_ret: CommandArtifact = self._run_sut_cmd(command)
        if cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.SWITCH,
                description=f"Error running SONiC command: `{command}`",
                data={
                    "command": command,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        return cmd_ret.stdout or ""

    # sub-collectors
    @classmethod
    def _parse_interface_status_line(cls, line: str) -> Optional[_ParsedInterfaceStatusLine]:
        """Parse one ``show interface status`` row."""
        stripped = line.strip()
        if not stripped.startswith("Ethernet"):
            return None
        match = cls._INTERFACE_STATUS_LINE_RE.match(stripped)
        if not match:
            return None
        return {
            "name": match.group("name"),
            "lanes": match.group("lanes"),
            "speed": match.group("speed"),
            "mtu": cls._to_int(match.group("mtu")),
            "fec": match.group("fec"),
            "alias": match.group("alias"),
            "vlan": match.group("vlan"),
            "oper": match.group("oper").lower(),
            "admin": match.group("admin").lower(),
            "type": match.group("type"),
            "asym_pfc": match.group("asym_pfc"),
        }

    def get_interface_status(self) -> Optional[Dict[str, SonicInterfaceStatus]]:
        """Parse ``show interface status`` into per-port status models.

        Returns:
            Mapping of port name to :class:`SonicInterfaceStatus`, or ``None``.
        """
        text = self._run_sonic_command(self.CMD_INTERFACE_STATUS)
        if text is None:
            return None
        result: Dict[str, SonicInterfaceStatus] = {}
        for line in text.splitlines():
            parsed = self._parse_interface_status_line(line)
            if parsed is None:
                continue
            name = str(parsed["name"])
            try:
                result[name] = SonicInterfaceStatus(**parsed)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build SonicInterfaceStatus for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_interface_counters(self) -> Optional[Dict[str, SonicInterfaceCounters]]:
        """Parse ``show interface counters`` into per-port counter models.

        Returns:
            Mapping of port name to :class:`SonicInterfaceCounters`, or ``None``.
        """
        text = self._run_sonic_command(self.CMD_INTERFACE_COUNTERS)
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<name>Ethernet\S*)"
            r"\s+(?P<state>\S+)"
            rf"\s+(?P<rx_ok>{_COUNT})"
            r"\s+(?P<rx_bps>[\d.,]+\s+\S*B/s)"
            r"\s+(?P<rx_util>\S+)"
            rf"\s+(?P<rx_err>{_COUNT})"
            rf"\s+(?P<rx_drp>{_COUNT})"
            rf"\s+(?P<rx_ovr>{_COUNT})"
            rf"\s+(?P<tx_ok>{_COUNT})"
            r"\s+(?P<tx_bps>[\d.,]+\s+\S*B/s)"
            r"\s+(?P<tx_util>\S+)"
            rf"\s+(?P<tx_err>{_COUNT})"
            rf"\s+(?P<tx_drp>{_COUNT})"
            rf"\s+(?P<tx_ovr>{_COUNT})"
            r"\s*$"
        )
        result: Dict[str, SonicInterfaceCounters] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("name")
            try:
                result[name] = SonicInterfaceCounters(
                    state=match.group("state"),
                    rx_ok=self._to_int(match.group("rx_ok")),
                    rx_bps=match.group("rx_bps"),
                    rx_util=match.group("rx_util"),
                    rx_err=self._to_int(match.group("rx_err")),
                    rx_drp=self._to_int(match.group("rx_drp")),
                    rx_ovr=self._to_int(match.group("rx_ovr")),
                    tx_ok=self._to_int(match.group("tx_ok")),
                    tx_bps=match.group("tx_bps"),
                    tx_util=match.group("tx_util"),
                    tx_err=self._to_int(match.group("tx_err")),
                    tx_drp=self._to_int(match.group("tx_drp")),
                    tx_ovr=self._to_int(match.group("tx_ovr")),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build SonicInterfaceCounters for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_fec_status(self) -> Optional[Dict[str, SonicFecStatus]]:
        """Parse ``show interface fec status`` into per-port FEC models.

        Returns:
            Mapping of port name to :class:`SonicFecStatus`, or ``None``.
        """
        text = self._run_sonic_command(self.CMD_FEC_STATUS)
        if text is None:
            return None
        line_pattern = re.compile(r"^(?P<name>Ethernet\S*)\s+(?P<oper>\S+)\s+(?P<admin>\S+)\s*$")
        result: Dict[str, SonicFecStatus] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("name")
            try:
                result[name] = SonicFecStatus(
                    oper=match.group("oper"),
                    admin=match.group("admin"),
                )
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build SonicFecStatus for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    def get_queue_counters(self) -> Optional[Dict[str, List[SonicQueueCounter]]]:
        """Parse ``show queue counters`` (``Eth*`` rows only) per port.

        Returns:
            Mapping of port name to a list of :class:`SonicQueueCounter`,
            or ``None``.
        """
        text = self._run_sonic_command(self.CMD_QUEUE_COUNTERS)
        if text is None:
            return None
        line_pattern = re.compile(
            r"^(?P<port>Ethernet\S*)"
            r"\s+(?P<txq>\S+)"
            rf"\s+(?P<pkts>{_COUNT})"
            rf"\s+(?P<bytes>{_COUNT})"
            rf"\s+(?P<drop_pkts>{_COUNT})"
            rf"\s+(?P<drop_bytes>{_COUNT})"
            r"\s*$"
        )
        result: Dict[str, List[SonicQueueCounter]] = {}
        for line in text.splitlines():
            match = line_pattern.match(line.strip())
            if not match:
                continue
            name = match.group("port")
            try:
                entry = SonicQueueCounter(
                    txq=match.group("txq"),
                    counter_pkts=self._to_int(match.group("pkts")),
                    counter_bytes=self._to_int(match.group("bytes")),
                    drop_pkts=self._to_int(match.group("drop_pkts")),
                    drop_bytes=self._to_int(match.group("drop_bytes")),
                )
                result.setdefault(name, []).append(entry)
            except (ValidationError, TypeError) as e:
                self._log_event(
                    category=EventCategory.SWITCH,
                    description=f"Failed to build SonicQueueCounter for {name}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
        return result or None

    # artifact-only collectors

    def collect_artifact_commands(self) -> None:
        """Run diagnostic commands so their output is captured in ``command_artifacts.json``.

        Each command is executed via :meth:`_run_sut_cmd`, which records the
        command, stdout, stderr and exit code as a ``CommandArtifact`` in
        ``command_artifacts.json``. No separate per-command ``.log`` files are
        written. Failures are logged but do **not** cause the overall
        collection to fail.
        """
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

    def _preflight_check(self) -> bool:
        """Verify the device is a reachable SONiC switch.

        Ensures the device responds and identifies as SONiC.

        On failure this sets ``self.result.status`` to
        :attr:`ExecutionStatus.NOT_RAN` and returns ``False``.

        Returns:
            ``True`` if the pre-flight check passed, ``False`` otherwise.
        """
        version_text = self._run_sonic_command(self.CMD_VERSION)
        if version_text is None:
            self._log_event(
                category=EventCategory.SWITCH,
                description="ScaleUpSonicCollector pre-flight check failed",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return False

        if not self._is_sonic_output(version_text):
            self._log_event(
                category=EventCategory.SWITCH,
                description="Not a SONiC switch",
                data={"raw_output": version_text},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return False

        return True

    # main entry point

    def collect_data(
        self, args: Optional[ScaleUpSonicCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ScaleUpSonicDataModel]]:
        """Run all SONiC collectors and assemble the switch data model.

        Args:
            args: Optional :class:`ScaleUpSonicCollectorArgs`.

        Returns:
            Tuple of ``(TaskResult, ScaleUpSonicDataModel | None)``.
        """

        if not self._preflight_check():
            return self.result, None

        try:
            interface_status = self.get_interface_status()
            interface_counters = self.get_interface_counters()
            fec_status = self.get_fec_status()
            queue_counters = self.get_queue_counters()

            self.collect_artifact_commands()
        except Exception as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Error running SONiC collector sub commands",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        all_port_names: set[str] = set()
        for source in (interface_status, interface_counters, fec_status, queue_counters):
            if source:
                all_port_names.update(source.keys())

        port_data: Optional[Dict[str, SonicPortData]] = None
        if all_port_names:
            port_data = {}
            for name in sorted(all_port_names):
                port_data[name] = SonicPortData(
                    interface_status=interface_status.get(name) if interface_status else None,
                    interface_counters=(
                        interface_counters.get(name) if interface_counters else None
                    ),
                    fec_status=fec_status.get(name) if fec_status else None,
                    queue_counters=queue_counters.get(name) if queue_counters else None,
                )

        try:
            sonic_data = ScaleUpSonicDataModel(
                port_list=sorted(all_port_names) if all_port_names else None,
                port=port_data,
            )
        except (ValidationError, TypeError) as e:
            self._log_event(
                category=EventCategory.SWITCH,
                description="Failed to build ScaleUpSonicDataModel",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        self.result.message = "SONiC switch data collected"
        return self.result, sonic_data
