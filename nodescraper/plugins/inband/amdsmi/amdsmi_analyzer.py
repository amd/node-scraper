###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
import io
from collections import defaultdict
from typing import Any, Optional, Union

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .amdsmidata import (
    AmdSmiDataModel,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiTstData,
    EccData,
    Fw,
    Partition,
    Processes,
    XgmiMetrics,
)
from .analyzer_args import AmdSmiAnalyzerArgs
from .cper import CperAnalysisTaskMixin


class AmdSmiAnalyzer(CperAnalysisTaskMixin, DataAnalyzer[AmdSmiDataModel, None]):
    """Check AMD SMI Application data for PCIe, ECC errors, CPER data, and analyze amdsmitst metrics"""

    DATA_MODEL = AmdSmiDataModel

    def check_expected_max_power(
        self,
        amdsmi_static_data: list[AmdSmiStatic],
        expected_max_power: int,
    ):
        """Check against expected max power

        Args:
            amdsmi_static_data (list[AmdSmiStatic]): AmdSmiStatic data model
            expected_max_power (int): expected max power
        """
        incorrect_max_power_gpus: dict[int, Union[int, str, float]] = {}
        for gpu in amdsmi_static_data:
            if gpu.limit is None or gpu.limit.max_power is None:
                self._log_event(
                    category=EventCategory.PLATFORM,
                    description=f"GPU: {gpu.gpu} has no max power limit set",
                    priority=EventPriority.WARNING,
                    data={"gpu": gpu.gpu},
                )
                continue
            max_power_value = gpu.limit.max_power.value
            try:
                max_power_float = float(max_power_value)
            except ValueError:
                self._log_event(
                    category=EventCategory.PLATFORM,
                    description=f"GPU: {gpu.gpu} has an invalid max power limit",
                    priority=EventPriority.ERROR,
                    data={
                        "gpu": gpu.gpu,
                        "max_power_value": max_power_value,
                    },
                )
                continue
            if max_power_float != expected_max_power:
                incorrect_max_power_gpus[gpu.gpu] = max_power_float
        if incorrect_max_power_gpus:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="Max power mismatch",
                priority=EventPriority.ERROR,
                data={
                    "gpus": list(incorrect_max_power_gpus.keys()),
                    "max_power_values": incorrect_max_power_gpus,
                    "expected_max_power": expected_max_power,
                },
            )

    def check_expected_driver_version(
        self,
        amdsmi_static_data: list[AmdSmiStatic],
        expected_driver_version: str,
    ) -> None:
        """Check expectecd driver version

        Args:
            amdsmi_static_data (list[AmdSmiStatic]): AmdSmiStatic data model
            expected_driver_version (str): expected driver version
        """
        bad_driver_gpus: list[int] = []

        versions_by_gpu: dict[int, Optional[str]] = {}
        for gpu in amdsmi_static_data:
            ver: Optional[str] = None
            if gpu.driver is not None:
                ver = gpu.driver.version
            versions_by_gpu[gpu.gpu] = ver
            if ver != expected_driver_version:
                bad_driver_gpus.append(gpu.gpu)

        if bad_driver_gpus:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="Driver Version Mismatch",
                priority=EventPriority.ERROR,
                data={
                    "gpus": bad_driver_gpus,
                    "driver_version": {g: versions_by_gpu[g] for g in bad_driver_gpus},
                    "expected_driver_version": expected_driver_version,
                },
            )

    def check_amdsmi_metric_pcie(
        self,
        amdsmi_metric_data: list[AmdSmiMetric],
        l0_to_recovery_count_error_threshold: int,
        l0_to_recovery_count_warning_threshold: int,
    ):
        """Check PCIe metrics for link errors

        Checks for PCIe link width, speed, replays, recoveries, and NAKs.
        Expected width/speeds should come from SKU info.

        Args:
            amdsmi_metric_data (list[AmdSmiMetric]): AmdSmiMetric data model
            l0_to_recovery_count_error_threshold (int): Threshold for error events
            l0_to_recovery_count_warning_threshold (int): Threshold for warning events
        """
        for metric in amdsmi_metric_data:
            pcie_data = metric.pcie
            gpu = metric.gpu

            if pcie_data.width is not None and pcie_data.width != 16:
                self._log_event(
                    category=EventCategory.IO,
                    description=f"GPU: {gpu} PCIe width is not x16",
                    priority=EventPriority.ERROR,
                    data={"gpu": gpu, "pcie_width": pcie_data.width, "expected": 16},
                    console_log=True,
                )

            if pcie_data.speed is not None and pcie_data.speed.value is not None:
                try:
                    speed_val = float(pcie_data.speed.value)
                    if speed_val != 32.0:
                        self._log_event(
                            category=EventCategory.IO,
                            description=f"GPU: {gpu} PCIe link speed is not Gen5 (32 GT/s)",
                            priority=EventPriority.ERROR,
                            data={"gpu": gpu, "pcie_speed": speed_val, "expected": 32.0},
                            console_log=True,
                        )
                except (ValueError, TypeError):
                    pass

            if pcie_data.replay_count is not None and pcie_data.replay_count > 0:
                self._log_event(
                    category=EventCategory.IO,
                    description=f"GPU: {gpu} has PCIe replay count: {pcie_data.replay_count}",
                    priority=EventPriority.WARNING,
                    data={"gpu": gpu, "replay_count": pcie_data.replay_count},
                    console_log=True,
                )

            if (
                pcie_data.replay_roll_over_count is not None
                and pcie_data.replay_roll_over_count > 0
            ):
                self._log_event(
                    category=EventCategory.IO,
                    description=f"GPU: {gpu} has PCIe replay rollover count: {pcie_data.replay_roll_over_count}",
                    priority=EventPriority.WARNING,
                    data={"gpu": gpu, "replay_roll_over_count": pcie_data.replay_roll_over_count},
                    console_log=True,
                )

            if pcie_data.l0_to_recovery_count is not None:
                if pcie_data.l0_to_recovery_count > l0_to_recovery_count_error_threshold:
                    self._log_event(
                        category=EventCategory.IO,
                        description=f"GPU: {gpu} has {pcie_data.l0_to_recovery_count} L0 recoveries",
                        priority=EventPriority.ERROR,
                        data={
                            "gpu": gpu,
                            "l0_to_recovery_count": pcie_data.l0_to_recovery_count,
                            "error_threshold": l0_to_recovery_count_error_threshold,
                        },
                        console_log=True,
                    )
                elif pcie_data.l0_to_recovery_count > l0_to_recovery_count_warning_threshold:
                    self._log_event(
                        category=EventCategory.IO,
                        description=f"GPU: {gpu} has {pcie_data.l0_to_recovery_count} L0 recoveries",
                        priority=EventPriority.WARNING,
                        data={
                            "gpu": gpu,
                            "l0_to_recovery_count": pcie_data.l0_to_recovery_count,
                            "warning_threshold": l0_to_recovery_count_warning_threshold,
                        },
                        console_log=True,
                    )

            if pcie_data.nak_sent_count is not None and pcie_data.nak_sent_count > 0:
                self._log_event(
                    category=EventCategory.IO,
                    description=f"GPU: {gpu} has sent {pcie_data.nak_sent_count} PCIe NAKs",
                    priority=EventPriority.WARNING,
                    data={"gpu": gpu, "nak_sent_count": pcie_data.nak_sent_count},
                    console_log=True,
                )

            if pcie_data.nak_received_count is not None and pcie_data.nak_received_count > 0:
                self._log_event(
                    category=EventCategory.IO,
                    description=f"GPU: {gpu} has received {pcie_data.nak_received_count} PCIe NAKs",
                    priority=EventPriority.WARNING,
                    data={"gpu": gpu, "nak_received_count": pcie_data.nak_received_count},
                    console_log=True,
                )

    def check_amdsmi_metric_ecc_totals(self, amdsmi_metric_data: list[AmdSmiMetric]):
        """Check ECC totals for all GPUs

        Raises errors for uncorrectable errors, warnings for correctable and deferred.

        Args:
            amdsmi_metric_data (list[AmdSmiMetric]): AmdSmiMetric data model
        """
        for metric in amdsmi_metric_data:
            ecc_totals = metric.ecc
            gpu = metric.gpu

            ecc_checks: list[tuple[EventPriority, Optional[int], str]] = [
                (
                    EventPriority.WARNING,
                    ecc_totals.total_correctable_count,
                    "Total correctable ECC errors",
                ),
                (
                    EventPriority.ERROR,
                    ecc_totals.total_uncorrectable_count,
                    "Total uncorrectable ECC errors",
                ),
                (
                    EventPriority.WARNING,
                    ecc_totals.total_deferred_count,
                    "Total deferred ECC errors",
                ),
                (
                    EventPriority.WARNING,
                    ecc_totals.cache_correctable_count,
                    "Cache correctable ECC errors",
                ),
                (
                    EventPriority.ERROR,
                    ecc_totals.cache_uncorrectable_count,
                    "Cache uncorrectable ECC errors",
                ),
            ]

            for priority, count, desc in ecc_checks:
                if count is not None and count > 0:
                    self._log_event(
                        category=EventCategory.RAS,
                        description="GPU ECC error count detected",
                        priority=priority,
                        data={"gpu": gpu, "error_count": count, "error_type": desc},
                        console_log=True,
                    )

    def check_amdsmi_metric_ecc(self, amdsmi_metric_data: list[AmdSmiMetric]):
        """Check ECC counts in all blocks for all GPUs

        Raises errors for uncorrectable errors, warnings for correctable and deferred.

        Args:
            amdsmi_metric_data (list[AmdSmiMetric]): AmdSmiMetric data model
        """
        for metric in amdsmi_metric_data:
            gpu = metric.gpu
            ecc_blocks = metric.ecc_blocks

            # Skip if ecc_blocks is a string (e.g., "N/A") or empty
            if isinstance(ecc_blocks, str) or not ecc_blocks:
                continue

            for block_name, ecc_data in ecc_blocks.items():
                if not isinstance(ecc_data, EccData):
                    continue

                if ecc_data.correctable_count is not None and ecc_data.correctable_count > 0:
                    self._log_event(
                        category=EventCategory.RAS,
                        description=f"GPU: {gpu} has correctable ECC errors in block {block_name}",
                        priority=EventPriority.WARNING,
                        data={
                            "gpu": gpu,
                            "block": block_name,
                            "correctable_count": ecc_data.correctable_count,
                        },
                        console_log=True,
                    )

                if ecc_data.uncorrectable_count is not None and ecc_data.uncorrectable_count > 0:
                    self._log_event(
                        category=EventCategory.RAS,
                        description=f"GPU: {gpu} has uncorrectable ECC errors in block {block_name}",
                        priority=EventPriority.ERROR,
                        data={
                            "gpu": gpu,
                            "block": block_name,
                            "uncorrectable_count": ecc_data.uncorrectable_count,
                        },
                        console_log=True,
                    )

                if ecc_data.deferred_count is not None and ecc_data.deferred_count > 0:
                    self._log_event(
                        category=EventCategory.RAS,
                        description=f"GPU: {gpu} has deferred ECC errors in block {block_name}",
                        priority=EventPriority.WARNING,
                        data={
                            "gpu": gpu,
                            "block": block_name,
                            "deferred_count": ecc_data.deferred_count,
                        },
                        console_log=True,
                    )

    def expected_gpu_processes(
        self, processes_data: Optional[list[Processes]], max_num_processes: int
    ):
        """Check the number of GPU processes running

        Args:
            processes_data (Optional[list[Processes]]): list of processes per GPU
            max_num_processes (int): max number of expected processes
        """
        gpu_exceeds_num_processes: dict[int, int] = {}
        if processes_data is None or len(processes_data) == 0:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No GPU processes data available",
                priority=EventPriority.WARNING,
                data={"processes_data": processes_data},
                console_log=True,
            )
            return
        for process in processes_data:
            if len(process.process_list) == 0 or isinstance(
                process.process_list[0].process_info, str
            ):
                # Skip if there are no processes
                continue

            process_count = len(process.process_list)
            if process_count > max_num_processes:
                gpu_exceeds_num_processes[process.gpu] = process_count

        if gpu_exceeds_num_processes:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="Number of processes exceeds max processes",
                priority=EventPriority.ERROR,
                data={
                    "gpu_exceeds_num_processes": gpu_exceeds_num_processes,
                },
                console_log=True,
            )

    def static_consistancy_check(self, amdsmi_static_data: list[AmdSmiStatic]):
        """Check consistency of expected data

        Args:
            amdsmi_static_data (list[AmdSmiStatic]): AmdSmiStatic data model
        """
        consistancy_data: dict[str, Union[set[str], set[int]]] = {
            "market_name": {gpu.asic.market_name for gpu in amdsmi_static_data},
            "vendor_id": {gpu.asic.vendor_id for gpu in amdsmi_static_data},
            "vendor_name": {gpu.asic.vendor_name for gpu in amdsmi_static_data},
            "subvendor_id": {gpu.asic.subvendor_id for gpu in amdsmi_static_data},
            "subsystem_id": {gpu.asic.subsystem_id for gpu in amdsmi_static_data},
            "device_id": {gpu.asic.device_id for gpu in amdsmi_static_data},
            "rev_id": {gpu.asic.rev_id for gpu in amdsmi_static_data},
            "num_compute_units": {str(gpu.asic.num_compute_units) for gpu in amdsmi_static_data},
            "target_graphics_version": {
                gpu.asic.target_graphics_version for gpu in amdsmi_static_data
            },
        }
        for key, value in consistancy_data.items():
            if len(value) > 1:
                self._log_event(
                    category=EventCategory.PLATFORM,
                    description=f"{key} is not consistent across all GPUs",
                    priority=EventPriority.WARNING,
                    data={
                        "field": key,
                        "non_consistent_values": value,
                    },
                )

    def check_static_data(
        self,
        amdsmi_static_data: list[AmdSmiStatic],
        vendor_id: Optional[str],
        subvendor_id: Optional[str],
        device_id: tuple[Optional[str], Optional[str]],
        subsystem_id: tuple[Optional[str], Optional[str]],
        sku_name: Optional[str],
    ) -> None:
        """Check expected static data

        Args:
            amdsmi_static_data (list[AmdSmiStatic]): AmdSmiStatic data
            vendor_id (Optional[str]): expected vendor_id
            subvendor_id (Optional[str]): expected subvendor_id
            device_id (tuple[Optional[str], Optional[str]]): expected device_id
            subsystem_id (tuple[Optional[str], Optional[str]]): expected subsystem_id
            sku_name (Optional[str]): expected sku_name
        """

        mismatches: list[tuple[int, str, str, str]] = []

        expected_data: dict[str, Optional[str]] = {
            "vendor_id": vendor_id,
            "subvendor_id": subvendor_id,
            "vendor_name": "Advanced Micro Devices Inc",
            "market_name": sku_name,
        }

        for gpu_data in amdsmi_static_data:
            collected_data: dict[str, str] = {
                "vendor_id": gpu_data.asic.vendor_id,
                "subvendor_id": gpu_data.asic.subvendor_id,
                "vendor_name": gpu_data.asic.vendor_name,
                "market_name": gpu_data.asic.market_name,
            }

            for key, expected in expected_data.items():
                if expected is None:
                    continue
                actual = collected_data[key]
                if expected not in actual:
                    mismatches.append((gpu_data.gpu, key, expected, actual))
                    break

            if device_id[0] is not None and device_id[1] is not None:
                dev_actual = gpu_data.asic.device_id
                if (
                    device_id[0].upper() not in dev_actual.upper()
                    and device_id[1].upper() not in dev_actual.upper()
                ):
                    mismatches.append(
                        (gpu_data.gpu, "device_id", f"{device_id[0]}|{device_id[1]}", dev_actual)
                    )

            if subsystem_id[0] is not None and subsystem_id[1] is not None:
                subsys_actual = gpu_data.asic.subsystem_id
                if (
                    subsystem_id[0].upper() not in subsys_actual.upper()
                    and subsystem_id[1].upper() not in subsys_actual.upper()
                ):
                    mismatches.append(
                        (
                            gpu_data.gpu,
                            "subsystem_id",
                            f"{subsystem_id[0]}|{subsystem_id[1]}",
                            subsys_actual,
                        )
                    )

        if mismatches:
            payload = self._format_static_mismatch_payload(mismatches)
            self._log_event(
                category=EventCategory.PLATFORM,
                description="amd-smi static data mismatch",
                priority=EventPriority.ERROR,
                data=payload,
            )

    def _format_static_mismatch_payload(
        self,
        mismatches: list[tuple[int, str, str, str]],
    ) -> dict[str, Any]:
        """Helper function for pretty printing mismatch in expected data

        Args:
            mismatches (list[tuple[int, str, str, str]]): mismatched data per GPU

        Returns:
            dict[str, Any]: dict of mismatched data per GPU
        """
        per_gpu: dict[int, list[dict[str, str]]] = defaultdict(list)
        field_set: set[str] = set()

        for gpu, field, expected, actual in mismatches:
            field_set.add(field)
            per_gpu[gpu].append({"field": field, "expected": expected, "actual": actual})

        per_gpu_list: list[dict[str, Any]] = [
            {"gpu": gpu, "mismatches": entries}
            for gpu, entries in sorted(per_gpu.items(), key=lambda kv: kv[0])
        ]

        return {
            "summary": {
                "gpus_affected": len(per_gpu),
                "fields": sorted(field_set),
                "total_mismatches": sum(len(v) for v in per_gpu.values()),
            },
            "per_gpu": per_gpu_list,
        }

    def check_pldm_version(
        self,
        amdsmi_fw_data: Optional[list[Fw]],
        expected_pldm_version: Optional[str],
    ):
        """Check expected pldm version

        Args:
            amdsmi_fw_data (Optional[list[Fw]]): data model
            expected_pldm_version (Optional[str]): expected pldm version
        """
        PLDM_STRING = "PLDM_BUNDLE"
        if amdsmi_fw_data is None or len(amdsmi_fw_data) == 0:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No AMD SMI firmware data available",
                priority=EventPriority.WARNING,
                data={"amdsmi_fw_data": amdsmi_fw_data},
            )
            return
        mismatched_gpus: list[int] = []
        pldm_missing_gpus: list[int] = []
        for fw_data in amdsmi_fw_data:
            gpu = fw_data.gpu
            if isinstance(fw_data.fw_list, str):
                pldm_missing_gpus.append(gpu)
                continue
            for fw_info in fw_data.fw_list:
                if PLDM_STRING == fw_info.fw_id and expected_pldm_version != fw_info.fw_version:
                    mismatched_gpus.append(gpu)
                if PLDM_STRING == fw_info.fw_id:
                    break
            else:
                pldm_missing_gpus.append(gpu)

        if mismatched_gpus or pldm_missing_gpus:
            self._log_event(
                category=EventCategory.FW,
                description="PLDM Version Mismatch",
                priority=EventPriority.ERROR,
                data={
                    "mismatched_gpus": mismatched_gpus,
                    "pldm_missing_gpus": pldm_missing_gpus,
                    "expected_pldm_version": expected_pldm_version,
                },
            )

    def check_expected_memory_partition_mode(
        self,
        partition_data: Optional[Partition],
        expected_memory_partition_mode: Optional[str],
        expected_compute_partition_mode: Optional[str],
    ):
        """Check expected mem partition mode

        Args:
            partition_data (Optional[Partition]): data model
            expected_memory_partition_mode (Optional[str]): expected mem partition mode
            expected_compute_partition_mode (Optional[str]): expected compute partition mode
        """
        if partition_data is None:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No AMD SMI Partition data not available",
                priority=EventPriority.WARNING,
            )
            return
        bad_memory_partition_mode_gpus = []
        for partition_current in partition_data.memory_partition:
            if (
                expected_memory_partition_mode is not None
                and partition_current.partition_type != expected_memory_partition_mode
            ):
                bad_memory_partition_mode_gpus.append(
                    {
                        "gpu_id": partition_current.gpu_id,
                        "memory_partition_mode": partition_current.partition_type,
                    }
                )

        for compute_current in partition_data.compute_partition:
            if (
                expected_compute_partition_mode is not None
                and compute_current.partition_type != expected_compute_partition_mode
            ):
                bad_memory_partition_mode_gpus.append(
                    {
                        "gpu_id": compute_current.gpu_id,
                        "compute_partition_mode": compute_current.partition_type,
                    }
                )

        if bad_memory_partition_mode_gpus:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="Partition Mode Mismatch",
                priority=EventPriority.ERROR,
                data={
                    "actual_partition_data": bad_memory_partition_mode_gpus,
                    "expected_memory_partition_mode": expected_memory_partition_mode,
                    "expected_compute_partition_mode": expected_compute_partition_mode,
                },
            )

    def check_expected_xgmi_link_speed(
        self,
        xgmi_metric: Optional[list[XgmiMetrics]],
        expected_xgmi_speed: Optional[list[float]] = None,
    ):
        """Check the XGMI link speed for all GPUs

        Args:
            xgmi_metric (Optional[list[XgmiMetrics]]): XGMI metrics data
            expected_xgmi_speed (Optional[list[float]]): List of expected XGMI speeds (GT/s)
        """
        if xgmi_metric is None or len(xgmi_metric) == 0:
            self._log_event(
                category=EventCategory.IO,
                description="XGMI link speed data is not available and cannot be checked",
                priority=EventPriority.WARNING,
                data={"xgmi_metric": xgmi_metric},
            )
            return

        if expected_xgmi_speed is None or len(expected_xgmi_speed) == 0:
            self._log_event(
                category=EventCategory.IO,
                description="Expected XGMI speed not configured, skipping XGMI link speed check",
                priority=EventPriority.WARNING,
            )
            return

        for xgmi_data in xgmi_metric:
            link_metric = xgmi_data.link_metrics
            try:
                if link_metric.bit_rate is None or link_metric.bit_rate.value is None:
                    self._log_event(
                        category=EventCategory.IO,
                        description="XGMI link speed is not available",
                        priority=EventPriority.ERROR,
                        data={
                            "gpu": xgmi_data.gpu,
                            "xgmi_bit_rate": (
                                link_metric.bit_rate.unit if link_metric.bit_rate else "N/A"
                            ),
                        },
                    )
                    continue

                xgmi_float = float(link_metric.bit_rate.value)
            except ValueError:
                self._log_event(
                    category=EventCategory.IO,
                    description="XGMI link speed is not a valid number",
                    priority=EventPriority.ERROR,
                    data={
                        "gpu": xgmi_data.gpu,
                        "xgmi_bit_rate": (
                            link_metric.bit_rate.value if link_metric.bit_rate else "N/A"
                        ),
                    },
                )
                continue

            if xgmi_float not in expected_xgmi_speed:
                self._log_event(
                    category=EventCategory.IO,
                    description="XGMI link speed is not as expected",
                    priority=EventPriority.ERROR,
                    data={
                        "gpu": xgmi_data.gpu,
                        "xgmi_bit_rate": xgmi_float,
                        "expected_xgmi_speed": expected_xgmi_speed,
                    },
                    console_log=True,
                )

    def check_amdsmitst(self, amdsmitst_data: AmdSmiTstData):
        """Check AMD SMI test results

        Args:
            amdsmitst_data (AmdSmiTstData): AMD SMI test data
        """
        if amdsmitst_data.failed_test_count > 0:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{amdsmitst_data.failed_test_count} failed tests running amdsmitst",
                priority=EventPriority.ERROR,
                data={
                    "failed_test_count": amdsmitst_data.failed_test_count,
                    "failed_tests": amdsmitst_data.failed_tests,
                },
                console_log=True,
            )

    def analyze_data(
        self, data: AmdSmiDataModel, args: Optional[AmdSmiAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the amdsmi data against expected data

        Args:
            data (AmdSmiDataModel): the AmdSmi data model
            args (_type_, optional): optional AmdSmi analyzer args. Defaults to None.

        Returns:
            TaskResult: the result of the analysis indicating weather the AmdSmi data model
            matched the expected data
        """

        if args is None:
            args = AmdSmiAnalyzerArgs()

        if data.metric is not None and len(data.metric) > 0:
            if args.l0_to_recovery_count_error_threshold is not None:
                self.check_amdsmi_metric_pcie(
                    data.metric,
                    args.l0_to_recovery_count_error_threshold,
                    args.l0_to_recovery_count_warning_threshold or 1,
                )
            self.check_amdsmi_metric_ecc_totals(data.metric)
            self.check_amdsmi_metric_ecc(data.metric)

        if args.expected_gpu_processes:
            self.expected_gpu_processes(data.process, args.expected_gpu_processes)

        if data.static is None or len(data.static) == 0:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No AMD SMI static data available",
                priority=EventPriority.WARNING,
                data={"amdsmi_static_data": data.static},
            )
        else:
            if args.expected_max_power:
                self.check_expected_max_power(data.static, args.expected_max_power)
            if args.expected_driver_version:
                self.check_expected_driver_version(data.static, args.expected_driver_version)

            self.static_consistancy_check(data.static)
            if (
                self.system_info.sku
                and args.devid_ep
                and args.devid_ep_vf
                and args.vendorid_ep
                and args.check_static_data
            ) or args.check_static_data:
                self.check_static_data(
                    data.static,
                    args.vendorid_ep,
                    args.vendorid_ep,
                    (args.devid_ep, args.devid_ep),
                    (args.devid_ep, args.devid_ep),
                    sku_name=args.sku_name,
                )

        if args.expected_memory_partition_mode or args.expected_compute_partition_mode:
            self.check_expected_memory_partition_mode(
                data.partition,
                args.expected_memory_partition_mode,
                args.expected_compute_partition_mode,
            )

        if args.expected_pldm_version:
            self.check_pldm_version(data.firmware, args.expected_pldm_version)

        if data.cper_data:
            self.analyzer_cpers(
                {
                    file_model_obj.file_name: io.BytesIO(file_model_obj.file_contents)
                    for file_model_obj in data.cper_data
                },
                analysis_range_start=args.analysis_range_start,
                analysis_range_end=args.analysis_range_end,
            )

        if data.xgmi_metric and len(data.xgmi_metric) > 0:
            self.check_expected_xgmi_link_speed(
                data.xgmi_metric, expected_xgmi_speed=args.expected_xgmi_speed
            )

        if data.amdsmitst_data and data.amdsmitst_data.failed_test_count > 0:
            self.check_amdsmitst(data.amdsmitst_data)

        return self.result
