###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""Analyzer for NicPlugin: checks Broadcom support_rdma, performance_profile, pcie_relaxed_ordering, getqos (QoS across adapters), and other expected values."""

from typing import Any, Dict, Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import NicAnalyzerArgs
from .nic_data import NicDataModel


def _normalize_prio_map(d: Optional[Dict[Any, Any]]) -> Optional[Dict[int, int]]:
    """Convert expected_qos_prio_map (config may have str keys) to Dict[int, int]."""
    if d is None:
        return None
    return {int(k): int(v) for k, v in d.items()}


def _normalize_tsa_map(d: Optional[Dict[Any, Any]]) -> Optional[Dict[int, str]]:
    """Convert expected_qos_tsa_map (config may have str keys) to Dict[int, str]."""
    if d is None:
        return None
    return {int(k): str(v) for k, v in d.items()}


class NicAnalyzer(DataAnalyzer[NicDataModel, NicAnalyzerArgs]):
    """Analyze niccli/nicctl data; checks Broadcom support_rdma, performance_profile (RoCE), pcie_relaxed_ordering (enabled), and getqos (expected QoS across adapters)."""

    DATA_MODEL = NicDataModel

    def analyze_data(
        self, data: NicDataModel, args: Optional[NicAnalyzerArgs] = None
    ) -> TaskResult:
        """Run checks on the collected data (Broadcom support_rdma, performance_profile, pcie_relaxed_ordering, getqos per device)."""
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

        # getqos: expected QoS (priorities, PFC, ETS) across all adapters
        any_qos_mismatch = False
        expected_prio = _normalize_prio_map(args.expected_qos_prio_map)
        expected_tsa = _normalize_tsa_map(args.expected_qos_tsa_map)
        if (
            expected_prio is not None
            or args.expected_qos_pfc_enabled is not None
            or expected_tsa is not None
            or args.expected_qos_tc_bandwidth is not None
        ):
            for device_num, qos in sorted(data.broadcom_nic_qos.items()):
                mismatches = []
                if expected_prio is not None and qos.prio_map != expected_prio:
                    mismatches.append(f"prio_map {qos.prio_map!r} != expected {expected_prio!r}")
                if (
                    args.expected_qos_pfc_enabled is not None
                    and qos.pfc_enabled != args.expected_qos_pfc_enabled
                ):
                    mismatches.append(
                        f"pfc_enabled {qos.pfc_enabled!r} != expected {args.expected_qos_pfc_enabled!r}"
                    )
                if expected_tsa is not None and qos.tsa_map != expected_tsa:
                    mismatches.append(f"tsa_map {qos.tsa_map!r} != expected {expected_tsa!r}")
                if (
                    args.expected_qos_tc_bandwidth is not None
                    and qos.tc_bandwidth != args.expected_qos_tc_bandwidth
                ):
                    mismatches.append(
                        f"tc_bandwidth {qos.tc_bandwidth!r} != expected {args.expected_qos_tc_bandwidth!r}"
                    )
                if mismatches:
                    any_qos_mismatch = True
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: getqos does not match expected QoS: {'; '.join(mismatches)}",
                        data={
                            "device_num": device_num,
                            "qos": qos.model_dump(),
                            "mismatches": mismatches,
                        },
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                else:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: getqos matches expected (priorities, PFC, ETS)",
                        data={"device_num": device_num},
                        priority=EventPriority.INFO,
                    )
        elif args.require_qos_consistent_across_adapters and len(data.broadcom_nic_qos) >= 2:
            qos_list = list(data.broadcom_nic_qos.values())
            first = qos_list[0]
            for device_num, qos in sorted(data.broadcom_nic_qos.items()):
                if (
                    qos.prio_map != first.prio_map
                    or qos.pfc_enabled != first.pfc_enabled
                    or qos.tsa_map != first.tsa_map
                ):
                    any_qos_mismatch = True
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: getqos differs from other adapters (priorities, PFC, or ETS not consistent)",
                        data={"device_num": device_num, "qos": qos.model_dump()},
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )
                else:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Broadcom device {device_num}: getqos consistent with other adapters",
                        data={"device_num": device_num},
                        priority=EventPriority.INFO,
                    )

        if any_disabled or any_non_roce or any_relaxed_ordering_bad or any_qos_mismatch:
            self.result.status = ExecutionStatus.WARNING
            parts = []
            if any_disabled:
                parts.append("support_rdma")
            if any_non_roce:
                parts.append("performance_profile")
            if any_relaxed_ordering_bad:
                parts.append("pcie_relaxed_ordering")
            if any_qos_mismatch:
                parts.append("getqos")
            self.result.message = f"Broadcom check(s) failed: {' and/or '.join(parts)}"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = "Broadcom support_rdma, performance_profile, pcie_relaxed_ordering, and getqos checks OK"
        return self.result
