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
import re
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.utils import bytes_to_human_readable, convert_to_bytes

from .analyzer_args import StorageAnalyzerArgs
from .storagedata import StorageDataModel


class StorageAnalyzer(DataAnalyzer[StorageDataModel, StorageAnalyzerArgs]):
    """Check storage usage"""

    DATA_MODEL = StorageDataModel

    def _matches_device_filter(
        self, device_name: str, exp_devices: list[str], regex_match: bool
    ) -> bool:
        """Check if the device name matches any of the expected devices""

        Args:
            device_name (str): device name to check
            exp_devices (list[str]): list of expected devices to match against
            regex_match (bool): if True, use regex matching; otherwise, use exact match

        Returns:
            bool: True if the device name matches any of the expected devices, False otherwise
        """
        for exp_device in exp_devices:
            if regex_match:
                try:
                    device_regex = re.compile(exp_device)
                except re.error:
                    self._log_event(
                        category=EventCategory.STORAGE,
                        description=f"Invalid regex pattern: {exp_device}",
                        priority=EventPriority.ERROR,
                    )
                    continue
                if device_regex.match(device_name):
                    return True
            elif device_name == exp_device:
                return True
        return False

    def analyze_data(
        self, data: StorageDataModel, args: Optional[StorageAnalyzerArgs] = None
    ) -> TaskResult:
        """Analyze the storage data to check if there is enough free space

        Args:
            data (StorageDataModel): storage data to analyze
            args (Optional[StorageAnalyzerArgs], optional): storage analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the storage analysis containing the status and message.
        """
        if args is None:
            args = StorageAnalyzerArgs(min_required_free_space_prct=10)
        elif args.min_required_free_space_abs is None and args.min_required_free_space_prct is None:
            args.min_required_free_space_prct = 10
            self.logger.warning(
                "No thresholds provided for storage analyzer arguments; defaulting to 10% free"
            )

        if not data.storage_data:
            self.result.message = "No storage data available"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        self.result.status = ExecutionStatus.OK
        fail = False
        passing_devices = []
        failing_devices = []
        for device_name, device_data in data.storage_data.items():
            if args.check_devices:
                if not self._matches_device_filter(
                    device_name, args.check_devices, args.regex_match
                ):
                    continue
            elif args.ignore_devices:
                if self._matches_device_filter(device_name, args.ignore_devices, args.regex_match):
                    continue

            condition = False
            if args.min_required_free_space_abs:
                min_free_abs = convert_to_bytes(args.min_required_free_space_abs)
                free_abs = convert_to_bytes(str(device_data.free))
                if free_abs and free_abs > min_free_abs:
                    condition = True
            else:
                condition = True

            if args.min_required_free_space_prct:
                free_prct = 100 - device_data.percent
                condition = condition and (free_prct > args.min_required_free_space_prct)

            if condition:
                passing_devices.append(
                    f"'{device_name}' has {bytes_to_human_readable(device_data.free)} available, {device_data.percent}% used"
                )
            else:
                fail = True
                device = convert_to_bytes(str(device_data.total))
                prct = device_data.percent
                failing_devices.append(f"{device_name}")
                event_data = {
                    "offending_device": {
                        "device": device_name,
                        "total": device_data.total,
                        "free": device_data.free,
                        "percent": device_data.percent,
                    },
                }
                self._log_event(
                    category=EventCategory.STORAGE,
                    description=f"{self.result.message} {bytes_to_human_readable(device)} and {prct}%,  used on {device_name}",
                    data=event_data,
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
        if fail:
            self.result.message = f"Insufficient disk space on " f"[{', '.join(failing_devices)}]"
            self.result.status = ExecutionStatus.ERROR
        else:
            self.result.message = ",".join(passing_devices)
        return self.result
