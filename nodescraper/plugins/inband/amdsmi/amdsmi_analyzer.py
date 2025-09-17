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


from nodescraper.enums import EventCategory, EventPriority
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .amdsmidata import AmdSmiDataModel, Fw, Partition, Processes
from .analyzer_args import AmdSmiAnalyzerArgs


class AmdSmiAnalyzer(DataAnalyzer[AmdSmiDataModel, None]):
    """"""

    DATA_MODEL = AmdSmiDataModel

    L0_TO_RECOVERY_COUNT_ERROR_THRESHOLD = 3
    L0_TO_RECOVERY_COUNT_WARNING_THRESHOLD = 1

    def expected_gpu_processes(
        self, processes_data: list[Processes] | None, max_num_processes: int
    ):
        """Check the number of GPU processes running. If the number of processes is greater than the expected
        number of processes, log an error event"""
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
                # Skip if there are no processes or the process info is a string which indicates no processes
                continue

            process_count = len(process.process_list)  # Number of processes for GPU
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

    def check_pldm_version(
        self,
        amdsmi_fw_data: list[Fw] | None,
        expected_pldm_version: str | None,
    ):
        """Check the PLDM version for all GPUs. If the PLDM version is not as expected, log an error event for which GPUs don't have a match"""
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
        partition_data: Partition | None,
        expected_memory_partition_mode: str | None,
        expected_compute_partition_mode: str | None,
    ):
        if partition_data is None:
            self._log_event(
                category=EventCategory.PLATFORM,
                description="No AMD SMI Partition data not available",
                priority=EventPriority.WARNING,
            )
            return
        bad_memory_partition_mode_gpus = []
        for partition_current in partition_data.current_partition:
            if (
                expected_memory_partition_mode is not None
                and partition_current.memory != expected_memory_partition_mode
            ) or (
                expected_compute_partition_mode is not None
                and partition_current.accelerator_type != expected_compute_partition_mode
            ):
                bad_memory_partition_mode_gpus.append(
                    {
                        "gpu_id": partition_current.gpu_id,
                        "compute_partition_mode": partition_current.accelerator_type,
                        "memory_partition_mode": partition_current.memory,
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

    def analyze_data(self, data: AmdSmiDataModel, args=None) -> TaskResult:

        if args is None:
            args = AmdSmiAnalyzerArgs()

        if args.expected_gpu_processes:
            self.expected_gpu_processes(data.process, args.expected_gpu_processes)
            if args.expected_memory_partition_mode or args.expected_compute_partition_mode:
                self.check_expected_memory_partition_mode(
                    data.partition,
                    args.expected_memory_partition_mode,
                    args.expected_compute_partition_mode,
                )

        return self.result
