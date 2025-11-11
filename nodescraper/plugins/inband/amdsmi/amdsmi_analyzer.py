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
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from nodescraper.enums import EventCategory, EventPriority
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .amdsmidata import AmdSmiDataModel, AmdSmiStatic, Fw, Partition, Processes
from .analyzer_args import AmdSmiAnalyzerArgs


class AmdSmiAnalyzer(DataAnalyzer[AmdSmiDataModel, None]):
    """"""

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
            "num_compute_units": {gpu.asic.num_compute_units for gpu in amdsmi_static_data},
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

        expected_data: Dict[str, Optional[str]] = {
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
        mismatches: List[tuple[int, str, str, str]],
    ) -> Dict[str, Any]:
        """Helper function for pretty printing mismatch in expected data

        Args:
            mismatches (List[tuple[int, str, str, str]]): mismatched data per GPU

        Returns:
            Dict[str, Any]: dict of mismatched data per GPU
        """
        per_gpu: Dict[int, List[Dict[str, str]]] = defaultdict(list)
        field_set: set[str] = set()

        for gpu, field, expected, actual in mismatches:
            field_set.add(field)
            per_gpu[gpu].append({"field": field, "expected": expected, "actual": actual})

        per_gpu_list: List[Dict[str, Any]] = [
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
            for fw_info in fw_data.fw_list:
                if PLDM_STRING == fw_info.fw_name and expected_pldm_version != fw_info.fw_version:
                    mismatched_gpus.append(gpu)
                if PLDM_STRING == fw_info.fw_name:
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

        # accelerator currently not avaialbe in API

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
            if args.expected_memory_partition_mode or args.expected_compute_partition_mode:
                self.check_expected_memory_partition_mode(
                    data.partition,
                    args.expected_memory_partition_mode,
                    args.expected_compute_partition_mode,
                )
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

        if args.expected_pldm_version:
            self.check_pldm_version(data.firmware, args.expected_pldm_version)

        return self.result
