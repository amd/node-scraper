###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""Analyzer for NicPlugin: checks Broadcom support_rdma, performance_profile, pcie_relaxed_ordering, and other expected values."""

from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import NicAnalyzerArgs
from .nic_data import NicDataModel


class NicAnalyzer(DataAnalyzer[NicDataModel, NicAnalyzerArgs]):
    """Analyze niccli/nicctl data; checks Broadcom support_rdma, performance_profile (RoCE), and pcie_relaxed_ordering (enabled)."""

    DATA_MODEL = NicDataModel

    def analyze_data(
        self, data: NicDataModel, args: Optional[NicAnalyzerArgs] = None
    ) -> TaskResult:
        """Run checks on the collected data (Broadcom support_rdma, performance_profile, pcie_relaxed_ordering per device)."""
        if args is None:
            args = NicAnalyzerArgs()
        if not data.broadcom_nic_support_rdma:
            self.result.message = "No Broadcom support_rdma data to check"
            self.result.status = ExecutionStatus.OK
            return self.result

        disabled_values = set(args.support_rdma_disabled_values)
        any_disabled = False
        for device_num, value in sorted(data.broadcom_nic_support_rdma.items()):
            value_lower = (value or "").strip().lower()
            if value_lower in disabled_values:
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

        # performance_profile expected value check (default RoCE)
        expected_profile = args.performance_profile_expected.strip()
        expected_profile_lower = expected_profile.lower()
        any_non_roce = False
        if data.broadcom_nic_performance_profile:
            for device_num, value in sorted(data.broadcom_nic_performance_profile.items()):
                value_normalized = (value or "").strip().lower()
                if value_normalized != expected_profile_lower:
                    any_non_roce = True
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: performance_profile is {value!r} (expected {expected_profile})",
                        data={"device_num": device_num, "performance_profile_output": value},
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                else:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: performance_profile = {expected_profile}",
                        data={"device_num": device_num, "performance_profile_output": value},
                        priority=EventPriority.INFO,
                    )

        # pcie_relaxed_ordering check (default: output should indicate "enabled")
        expected_ro = args.pcie_relaxed_ordering_expected.strip().lower()
        any_relaxed_ordering_bad = False
        if data.broadcom_nic_pcie_relaxed_ordering and expected_ro:
            for device_num, value in sorted(data.broadcom_nic_pcie_relaxed_ordering.items()):
                value_lower = (value or "").strip().lower()
                if expected_ro not in value_lower:
                    any_relaxed_ordering_bad = True
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: pcie_relaxed_ordering does not show {args.pcie_relaxed_ordering_expected!r} (got {value!r})",
                        data={"device_num": device_num, "pcie_relaxed_ordering_output": value},
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                else:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: pcie_relaxed_ordering = {args.pcie_relaxed_ordering_expected}",
                        data={"device_num": device_num, "pcie_relaxed_ordering_output": value},
                        priority=EventPriority.INFO,
                    )

        if any_disabled or any_non_roce or any_relaxed_ordering_bad:
            self.result.status = ExecutionStatus.WARNING
            parts = []
            if any_disabled:
                parts.append("support_rdma")
            if any_non_roce:
                parts.append("performance_profile")
            if any_relaxed_ordering_bad:
                parts.append("pcie_relaxed_ordering")
            self.result.message = f"Broadcom check(s) failed: {' and/or '.join(parts)}"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = (
                "Broadcom support_rdma, performance_profile, and pcie_relaxed_ordering checks OK"
            )
        return self.result
