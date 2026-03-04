###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################

from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import NicAnalyzerArgs
from .niccli_data import NicDataModel

SUPPORT_RDMA_DISABLED_VALUES = frozenset({"0", "false", "disabled", "no", "off"})


class NicAnalyzer(DataAnalyzer[NicDataModel, NicAnalyzerArgs]):
    """Analyze niccli/nicctl data;"""

    DATA_MODEL = NicDataModel

    def analyze_data(
        self, data: NicDataModel, args: Optional[NicAnalyzerArgs] = None
    ) -> TaskResult:
        """Run checks on the collected data (e.g. Broadcom support_rdma per device)."""
        if not data.broadcom_nic_support_rdma:
            self.result.message = "No Broadcom support_rdma data to check"
            self.result.status = ExecutionStatus.OK
            return self.result

        any_disabled = False
        for device_num, value in sorted(data.broadcom_nic_support_rdma.items()):
            value_lower = (value or "").strip().lower()
            if value_lower in SUPPORT_RDMA_DISABLED_VALUES:
                any_disabled = True
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Broadcom device {device_num}: support_rdma is disabled or off",
                    data={"device_num": device_num, "support_rdma_output": value},
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
            else:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Broadcom device {device_num}: support_rdma = {value!r}",
                    data={"device_num": device_num, "support_rdma_output": value},
                    priority=EventPriority.INFO,
                )

        if any_disabled:
            self.result.message = "One or more Broadcom devices have support_rdma disabled"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = "Broadcom support_rdma check OK"
            self.result.status = ExecutionStatus.OK
        return self.result
