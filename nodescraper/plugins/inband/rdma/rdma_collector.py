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
from typing import Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_traceback

from .rdmadata import RdmaDataModel, RdmaDevice, RdmaLink, RdmaLinkText, RdmaStatistics


class RdmaCollector(InBandDataCollector[RdmaDataModel, None]):
    """Collect RDMA status and statistics via rdma link and rdma statistic commands."""

    DATA_MODEL = RdmaDataModel
    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    CMD_LINK = "rdma link -j"
    CMD_STATISTIC = "rdma statistic -j"
    CMD_RDMA_DEV = "rdma dev"
    CMD_RDMA_LINK = "rdma link"

    def _run_rdma_command(self, cmd: str) -> Optional[list[dict]]:
        """Run rdma command with JSON output.

        Args:
            cmd: Full command string (e.g. CMD_LINK or CMD_STATISTIC).

        Returns:
            List of dicts from JSON output, or None on failure.
        """
        res = self._run_sut_cmd(cmd)

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Error running rdma command: {cmd}",
                data={
                    "command": cmd,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None

        if not res.stdout.strip():
            return []

        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError as e:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Error parsing command: {cmd} json data",
                data={
                    "cmd": cmd,
                    "exception": get_exception_traceback(e),
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None

    def _parse_rdma_dev(self, output: str) -> list[RdmaDevice]:
        """Parse 'rdma dev' output into RdmaDevice objects."""
        devices = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            device_name = None
            start_idx = 0
            if parts[0].endswith(":"):
                start_idx = 1
            if start_idx < len(parts):
                device_name = parts[start_idx].rstrip(":")
                start_idx += 1
            if not device_name:
                continue
            device = RdmaDevice(device=device_name)
            i = start_idx
            while i < len(parts):
                if parts[i] == "node_type" and i + 1 < len(parts):
                    device.node_type = parts[i + 1]
                    i += 2
                elif parts[i] == "fw" and i + 1 < len(parts):
                    device.attributes["fw_version"] = parts[i + 1]
                    i += 2
                elif parts[i] == "node_guid" and i + 1 < len(parts):
                    device.node_guid = parts[i + 1]
                    i += 2
                elif parts[i] == "sys_image_guid" and i + 1 < len(parts):
                    device.sys_image_guid = parts[i + 1]
                    i += 2
                elif parts[i] == "state" and i + 1 < len(parts):
                    device.state = parts[i + 1]
                    i += 2
                else:
                    if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                        device.attributes[parts[i]] = parts[i + 1]
                        i += 2
                    else:
                        i += 1
            devices.append(device)
        return devices

    def _parse_rdma_link_text(self, output: str) -> list[RdmaLinkText]:
        """Parse 'rdma link' (text) output into RdmaLinkText objects."""
        links = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.search(r"(\S+)/(\d+)", line)
            if not match:
                continue
            device_name = match.group(1)
            port = int(match.group(2))
            link = RdmaLinkText(device=device_name, port=port)
            parts = line.split()
            i = 0
            while i < len(parts):
                if parts[i] == "state" and i + 1 < len(parts):
                    link.state = parts[i + 1]
                    i += 2
                elif parts[i] == "physical_state" and i + 1 < len(parts):
                    link.physical_state = parts[i + 1]
                    i += 2
                elif parts[i] == "netdev" and i + 1 < len(parts):
                    link.netdev = parts[i + 1]
                    i += 2
                else:
                    if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                        link.attributes[parts[i]] = parts[i + 1]
                        i += 2
                    else:
                        i += 1
            links.append(link)
        return links

    def _get_rdma_statistics(self) -> Optional[list[RdmaStatistics]]:
        """Get RDMA statistics from 'rdma statistic -j'."""
        stat_data = self._run_rdma_command(self.CMD_STATISTIC)
        if stat_data is None:
            return None
        if not stat_data:
            return []

        try:
            statistics = []
            for stat in stat_data:
                if not isinstance(stat, dict):
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description="Invalid data type for RDMA statistic",
                        data={"data_type": type(stat).__name__},
                        priority=EventPriority.WARNING,
                    )
                    continue
                statistics.append(RdmaStatistics(**stat))
        except ValidationError as e:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Failed to build RdmaStatistics model",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
        return statistics

    def _get_rdma_link(self) -> Optional[list[RdmaLink]]:
        """Get RDMA link data from 'rdma link -j'."""
        link_data = self._run_rdma_command(self.CMD_LINK)
        if link_data is None:
            return None
        if not link_data:
            return []

        try:
            links = []
            for link in link_data:
                if not isinstance(link, dict):
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description="Invalid data type for RDMA link",
                        data={"data_type": type(link).__name__},
                        priority=EventPriority.WARNING,
                    )
                    continue
                links.append(RdmaLink(**link))
            return links
        except ValidationError as e:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Failed to build RdmaLink model",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
        return links

    def collect_data(self, args: None = None) -> tuple[TaskResult, Optional[RdmaDataModel]]:
        """Collect RDMA statistics, link data, and device/link text output.

        Returns:
            Task result and RdmaDataModel, or None if all commands failed.
        """
        try:
            links = self._get_rdma_link()
            statistics = self._get_rdma_statistics()

            dev_list: list[RdmaDevice] = []
            res_rdma_dev = self._run_sut_cmd(self.CMD_RDMA_DEV)
            if res_rdma_dev.exit_code == 0:
                dev_list = self._parse_rdma_dev(res_rdma_dev.stdout)
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Collected {len(dev_list)} RDMA devices from 'rdma dev'",
                    priority=EventPriority.INFO,
                )
            else:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description="Error or no output from 'rdma dev'",
                    data={"command": self.CMD_RDMA_DEV, "exit_code": res_rdma_dev.exit_code},
                    priority=EventPriority.WARNING,
                )

            link_list_text: list[RdmaLinkText] = []
            res_rdma_link = self._run_sut_cmd(self.CMD_RDMA_LINK)
            if res_rdma_link.exit_code == 0:
                link_list_text = self._parse_rdma_link_text(res_rdma_link.stdout)
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Collected {len(link_list_text)} RDMA links from 'rdma link'",
                    priority=EventPriority.INFO,
                )
            else:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description="Error or no output from 'rdma link'",
                    data={"command": self.CMD_RDMA_LINK, "exit_code": res_rdma_link.exit_code},
                    priority=EventPriority.WARNING,
                )

            if statistics is None and links is None and not dev_list and not link_list_text:
                self.result.status = ExecutionStatus.EXECUTION_FAILURE
                self.result.message = "Failed to collect RDMA data"
                return self.result, None

            rdma_data = RdmaDataModel(
                statistic_list=statistics if statistics is not None else [],
                link_list=links if links is not None else [],
                dev_list=dev_list,
                link_list_text=link_list_text,
            )
            if (
                not rdma_data.statistic_list
                and not rdma_data.link_list
                and not rdma_data.dev_list
                and not rdma_data.link_list_text
            ):
                self.result.status = ExecutionStatus.WARNING
                self.result.message = "No RDMA devices found"
                return self.result, None

            self.result.message = (
                f"Collected {len(rdma_data.statistic_list)} RDMA statistics, "
                f"{len(rdma_data.link_list)} RDMA links (JSON), "
                f"{len(rdma_data.dev_list)} devices, {len(rdma_data.link_list_text)} links (text)"
            )
            self.result.status = ExecutionStatus.OK
            return self.result, rdma_data

        except Exception as e:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error running RDMA collector",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None
