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
from typing import Any, Dict, Optional

from nodescraper.base.regexanalyzer import RegexAnalyzer
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .analyzer_args import NetworkAnalyzerArgs
from .networkdata import NetworkDataModel


def _validate_firmware_policy(records: list[Dict[str, Any]], policies: Any) -> list[Dict[str, Any]]:
    """Validate ethtool firmware locally against this analyzer's policies."""
    policy_list = [policies] if isinstance(policies, dict) else policies or []
    issues = []
    for record in records:
        policy = next(
            (
                item
                for item in policy_list
                if isinstance(item, dict) and _policy_matches(record, item)
            ),
            None,
        )
        if policy is None:
            continue
        actual = _normalize_firmware_version(record.get("version"))
        expected = _normalize_firmware_version(policy.get("expected_nic_firmware"))
        if not actual:
            reason = "firmware version is unavailable"
        elif expected and actual != expected:
            reason = (
                f"actual {record.get('version')} != expected_nic_firmware "
                f"{policy.get('expected_nic_firmware')}"
            )
        else:
            continue
        issues.append({"reason": reason, "record": record, "policy": dict(policy)})
    return issues


def _policy_matches(record: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    match = policy.get("match", {})
    if not isinstance(match, dict):
        return False
    if not match:
        match = {field: policy[field] for field in record if field in policy}
    for field, expected in match.items():
        actual = record.get(str(field))
        if actual is None:
            return False
        expected_values = expected if isinstance(expected, list) else [expected]
        if not any(
            str(actual).strip().lower() == str(value).strip().lower() for value in expected_values
        ):
            return False
    return True


def _normalize_firmware_version(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().strip("'\"").lower()
    return normalized or None


class NetworkAnalyzer(RegexAnalyzer[NetworkDataModel, NetworkAnalyzerArgs]):
    """Check network statistics for errors."""

    DATA_MODEL = NetworkDataModel

    def analyze_data(
        self, data: NetworkDataModel, args: Optional[NetworkAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze ethtool -S statistics via RDMA-scoped vendor models.

        Args:
            data: Network data model with ethtool_statistics.
            args: Unused; retained for analyzer interface compatibility.

        Returns:
            TaskResult with OK, WARNING (no devices, or only warning-tier counters), or ERROR.
        """
        args = args or NetworkAnalyzerArgs()
        firmware_records = []
        for interface, info in data.ethtool_info.items():
            vendor = _vendor_for_driver(info.driver)
            if vendor is None:
                continue
            firmware_records.append(
                {
                    "identity": interface,
                    "version": info.firmware_version,
                    "source": "ethtool",
                    "vendor": vendor,
                    "driver": info.driver,
                    "interface": interface,
                    "pci_bdf": info.bus_info,
                }
            )
        firmware_policy_issues = _validate_firmware_policy(
            firmware_records,
            (
                {"expected_nic_firmware": args.expected_nic_firmware}
                if args.expected_nic_firmware
                else None
            ),
        )
        for issue in firmware_policy_issues:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Network adapter firmware policy mismatch",
                data=issue,
                priority=EventPriority.WARNING,
                console_log=True,
            )

        if not data.ethtool_info and not data.ethtool_statistics:
            self.result.message = "No network devices found"
            self.result.status = ExecutionStatus.WARNING
            return self.result

        vendor_error = False
        vendor_warning = False
        vendor_error_fields: set[str] = set()
        vendor_warning_fields: set[str] = set()
        vendor_queue_error_fields: set[str] = set()
        vendor_queue_warning_fields: set[str] = set()
        for stat in data.ethtool_statistics:
            if stat.vendor_statistics is None:
                continue

            vs = stat.vendor_statistics
            error_fields = vs.error_fields
            warning_fields = vs.warning_fields

            for field_name in error_fields + warning_fields:
                error_value = getattr(vs, field_name, None)
                if error_value is not None and error_value > 0:
                    is_warning_tier = field_name in warning_fields
                    priority = EventPriority.WARNING if is_warning_tier else EventPriority.ERROR
                    if is_warning_tier:
                        vendor_warning = True
                        vendor_warning_fields.add(field_name)
                    else:
                        vendor_error = True
                        vendor_error_fields.add(field_name)
                    # Use a single grouped description per severity
                    desc = (
                        "Ethtool warning detected" if is_warning_tier else "Ethtool error detected"
                    )
                    # Per-field events are still recorded for the run summary and event
                    # log, but console logging is suppressed here
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=desc,
                        data={
                            "netdev": stat.netdev,
                            "driver": stat.driver,
                            "error_field": field_name,
                            "error_count": error_value,
                        },
                        priority=priority,
                        console_log=False,
                    )

            # Per-queue counters matched against the vendor's adjustable regex
            queue_error_patterns = [
                re.compile(pattern) for pattern in getattr(type(vs), "queue_error_regex", [])
            ]
            queue_warning_patterns = [
                re.compile(pattern) for pattern in getattr(type(vs), "queue_warning_regex", [])
            ]
            if stat.queue_statistics and (queue_error_patterns or queue_warning_patterns):
                for counter_name, counter_value in stat.queue_statistics.items():
                    if counter_value <= 0:
                        continue
                    if queue_error_patterns and any(
                        pattern.search(counter_name) for pattern in queue_error_patterns
                    ):
                        vendor_error = True
                        vendor_queue_error_fields.add(f"{stat.netdev} {counter_name}")
                        self._log_event(
                            category=EventCategory.NETWORK,
                            description="Ethtool queue error detected",
                            data={
                                "netdev": stat.netdev,
                                "driver": stat.driver,
                                "error_field": counter_name,
                                "error_count": counter_value,
                            },
                            priority=EventPriority.ERROR,
                            console_log=False,
                        )
                    elif queue_warning_patterns and any(
                        pattern.search(counter_name) for pattern in queue_warning_patterns
                    ):
                        vendor_warning = True
                        vendor_queue_warning_fields.add(f"{stat.netdev} {counter_name}")
                        self._log_event(
                            category=EventCategory.NETWORK,
                            description="Ethtool queue warning detected",
                            data={
                                "netdev": stat.netdev,
                                "driver": stat.driver,
                                "error_field": counter_name,
                                "error_count": counter_value,
                            },
                            priority=EventPriority.WARNING,
                            console_log=False,
                        )

        if vendor_error_fields:
            self.logger.error("Ethtool error detected: %s", ", ".join(sorted(vendor_error_fields)))
        if vendor_queue_error_fields:
            self.logger.error(
                "Ethtool queue error detected: %s",
                ", ".join(sorted(vendor_queue_error_fields)),
            )
        if vendor_warning_fields:
            self.logger.warning(
                "Ethtool warning detected: %s", ", ".join(sorted(vendor_warning_fields))
            )
        if vendor_queue_warning_fields:
            self.logger.warning(
                "Ethtool queue warning detected: %s",
                ", ".join(sorted(vendor_queue_warning_fields)),
            )

        if vendor_error:
            self.result.message = "Network errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        elif vendor_warning:
            self.result.message = "Network warning counters non-zero in statistics"
            self.result.status = ExecutionStatus.WARNING
        elif firmware_policy_issues:
            self.result.message = "Network adapter firmware policy mismatch"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = "No network errors detected in statistics"
            self.result.status = ExecutionStatus.OK

        return self.result


def _vendor_for_driver(driver: Optional[str]) -> Optional[str]:
    """Return a stable vendor label for common ethtool driver families."""
    if not driver:
        return None
    normalized = driver.lower()
    if normalized.startswith(("bnxt", "bnx2")):
        return "Broadcom"
    if normalized.startswith(("mlx", "ib_")):
        return "Mellanox"
    if normalized.startswith(("ionic",)):
        return "Pensando"
    return None
