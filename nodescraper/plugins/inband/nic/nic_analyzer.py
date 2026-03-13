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
from typing import Any, Dict, List, Optional

from nodescraper.base.regexanalyzer import ErrorRegex
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import NicAnalyzerArgs
from .nic_data import NicDataModel

# Default regexes for nicctl show card logs (boot-fault, persistent, non-persistent)
DEFAULT_NICCTL_LOG_ERROR_REGEX: List[ErrorRegex] = [
    ErrorRegex(
        regex=re.compile(r"\berror\b", re.IGNORECASE),
        message="nicctl card log: error",
        event_category=EventCategory.NETWORK,
        event_priority=EventPriority.WARNING,
    ),
    ErrorRegex(
        regex=re.compile(r"\bfail(?:ed|ure)?\b", re.IGNORECASE),
        message="nicctl card log: fail/failed/failure",
        event_category=EventCategory.NETWORK,
        event_priority=EventPriority.WARNING,
    ),
    ErrorRegex(
        regex=re.compile(r"\bfault\b", re.IGNORECASE),
        message="nicctl card log: fault",
        event_category=EventCategory.NETWORK,
        event_priority=EventPriority.WARNING,
    ),
    ErrorRegex(
        regex=re.compile(r"\bcritical\b", re.IGNORECASE),
        message="nicctl card log: critical",
        event_category=EventCategory.NETWORK,
        event_priority=EventPriority.WARNING,
    ),
]


def _nicctl_log_error_regex_list(
    args: NicAnalyzerArgs,
) -> List[ErrorRegex]:
    """Return list of ErrorRegex for nicctl card logs (from args or default)."""
    if not args.nicctl_log_error_regex:
        return list(DEFAULT_NICCTL_LOG_ERROR_REGEX)
    out: List[ErrorRegex] = []
    for item in args.nicctl_log_error_regex:
        if isinstance(item, ErrorRegex):
            out.append(item)
        elif isinstance(item, dict):
            d = dict(item)
            d["regex"] = re.compile(d["regex"]) if isinstance(d.get("regex"), str) else d["regex"]
            if "event_category" in d and isinstance(d["event_category"], str):
                d["event_category"] = EventCategory(d["event_category"])
            if "event_priority" in d:
                p = d["event_priority"]
                if isinstance(p, str):
                    d["event_priority"] = getattr(EventPriority, p.upper(), EventPriority.WARNING)
                elif isinstance(p, int):
                    d["event_priority"] = EventPriority(p)
            out.append(ErrorRegex(**d))
    return out


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

        has_broadcom = bool(data.broadcom_nic_support_rdma)
        has_nicctl_logs = bool(
            data.nicctl_card_logs and any((c or "").strip() for c in data.nicctl_card_logs.values())
        )
        if not has_broadcom and not has_nicctl_logs:
            self.result.message = "No Broadcom support_rdma or nicctl card log data to check"
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
                if expected_profile_lower not in value_normalized:
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

        # nicctl card logs (boot-fault, persistent, non-persistent): run error regexes and log matches to user.
        any_nicctl_log_errors = False
        if data.nicctl_card_logs:
            regex_list = _nicctl_log_error_regex_list(args)
            for log_type, content in data.nicctl_card_logs.items():
                if not (content or "").strip():
                    continue
                for err_regex in regex_list:
                    for match in err_regex.regex.finditer(content):
                        matched_text = match.group(0).strip() or match.group(0)
                        if len(matched_text) > 500:
                            matched_text = matched_text[:497] + "..."
                        any_nicctl_log_errors = True
                        self._log_event(
                            category=err_regex.event_category,
                            description=f"nicctl card log ({log_type}): {err_regex.message} — {matched_text!r}",
                            data={
                                "log_type": log_type,
                                "message": err_regex.message,
                                "match_content": matched_text,
                            },
                            priority=err_regex.event_priority,
                            console_log=True,
                        )

        if (
            any_disabled
            or any_non_roce
            or any_relaxed_ordering_bad
            or any_qos_mismatch
            or any_nicctl_log_errors
        ):
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
            if any_nicctl_log_errors:
                parts.append("nicctl_card_logs")
            self.result.message = f"Broadcom/nic check(s) failed: {' and/or '.join(parts)}"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = "Broadcom support_rdma, performance_profile, pcie_relaxed_ordering, getqos, and nicctl card logs checks OK"
        return self.result
