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
from typing import Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_traceback

from .rdmadata import RdmaDataModel, RdmaLink, RdmaStatistics


class RdmaCollector(InBandDataCollector[RdmaDataModel, None]):
    """Collect RDMA status and statistics via rdma link and rdma statistic commands."""

    DATA_MODEL = RdmaDataModel
    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    CMD_LINK = "rdma link -j"
    CMD_STATISTIC = "rdma statistic -j"

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
        """Collect RDMA statistics and link data.

        Returns:
            Task result and RdmaDataModel, or None if both commands failed.
        """
        try:
            links = self._get_rdma_link()
            statistics = self._get_rdma_statistics()

            if statistics is None and links is None:
                self.result.status = ExecutionStatus.EXECUTION_FAILURE
                self.result.message = "Failed to collect RDMA data"
                return self.result, None

            rdma_data = RdmaDataModel(
                statistic_list=statistics if statistics is not None else [],
                link_list=links if links is not None else [],
            )
            self.result.message = (
                f"Collected {len(rdma_data.statistic_list)} RDMA statistics, "
                f"{len(rdma_data.link_list)} RDMA links"
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
