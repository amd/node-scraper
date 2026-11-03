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
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RedfishInventoryAnalyzerArgs
from .firmware_compare import (
    firmware_components,
    firmware_mismatches,
    firmware_target_text,
)
from .inventory_data import RedfishInventoryDataModel


class RedfishInventoryAnalyzer(
    DataAnalyzer[RedfishInventoryDataModel, RedfishInventoryAnalyzerArgs]
):
    """Compare FirmwareInventory members across the targets this plugin collected."""

    DATA_MODEL = RedfishInventoryDataModel

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "analysis_args.compare_firmware defaults to true and compares FirmwareInventory "
        "across the targets this plugin connected.",
        "RedfishInventoryPlugin compares its direct Redfish targets. "
        "AmcRedfishInventoryPlugin compares its SSH-proxy targets. The two are not mixed.",
        "A different Version, a member missing on a connected target, or a missing or empty "
        "Version (recorded as N/A) logs one FW warning per component.",
        "Each warning records Version, Status Health, Status State, SoftwareId, Updateable, "
        "and Oem SVN. The component id is the published Id and is not normalized.",
        "Warnings are written to the analyzer events.json. result.json has the summary count. "
        "The console summary is that count, not the per-component table.",
        "Fewer than two connected targets, a target that failed to connect, or "
        "compare_firmware false does not warn. --data loads one model and does not compare nodes.",
        "When no FirmwareInventory members were collected, one warning says the comparison did not run.",
    )

    def analyze_data(
        self,
        data: RedfishInventoryDataModel,
        args: Optional[RedfishInventoryAnalyzerArgs] = None,
    ) -> TaskResult:
        """Compare firmware for a single collected inventory model.

        Args:
            data: Inventory collected from one target.
            args: Analyzer arguments. Defaults to comparing firmware.

        Returns:
            TaskResult: OK because one model has no other target to compare.
        """
        self._apply_firmware_comparison({"target": data}, args or RedfishInventoryAnalyzerArgs())
        return self.result

    def compare_firmware(
        self,
        targets: dict[str, RedfishInventoryDataModel],
        args: Optional[RedfishInventoryAnalyzerArgs] = None,
    ) -> TaskResult:
        """Compare firmware across every target collected by one plugin.

        Args:
            targets: Target key to the inventory collected from that target.
            args: Analyzer arguments. Defaults to comparing firmware.

        Returns:
            TaskResult: WARNING when firmware differs, otherwise OK or NOT_RAN.
        """
        self.result = self._init_result()
        self._apply_firmware_comparison(targets, args or RedfishInventoryAnalyzerArgs())
        result = self.result
        result.finalize(self.logger)
        sample = next(iter(targets.values()), None)
        self._run_hooks(result, data=sample)
        return result

    def _apply_firmware_comparison(
        self,
        targets: dict[str, RedfishInventoryDataModel],
        args: RedfishInventoryAnalyzerArgs,
    ) -> None:
        """Set the analysis result for a firmware comparison.

        Args:
            targets: Target key to the inventory collected from that target.
            args: Analyzer arguments.

        Returns:
            None.
        """
        if not args.compare_firmware:
            self.result.status = ExecutionStatus.OK
            self.result.message = "Firmware comparison disabled"
            return
        if not targets:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "No Redfish inventory available to compare"
            return
        if len(targets) < 2:
            self.result.status = ExecutionStatus.OK
            self.result.message = "Firmware comparison needs at least two connected targets"
            return

        by_target = {key: firmware_components(model) for key, model in targets.items()}
        if not any(by_target.values()):
            self._log_event(
                category=EventCategory.FW,
                description=(
                    "Firmware comparison did not run: no FirmwareInventory members were collected"
                ),
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.WARNING
            self.result.message = "No FirmwareInventory members were collected"
            return

        mismatches = firmware_mismatches(by_target)
        for mismatch in mismatches:
            parts = [
                f"{target}={firmware_target_text(record)}"
                for target, record in mismatch["targets"].items()
            ]
            description = f"Firmware {mismatch['firmware_id']} differs: " + ", ".join(parts)
            self._log_event(
                category=EventCategory.FW,
                description=description,
                data={
                    "firmware_id": mismatch["firmware_id"],
                    "targets": mismatch["targets"],
                },
                priority=EventPriority.WARNING,
                console_log=True,
            )
        if mismatches:
            self.result.status = ExecutionStatus.WARNING
            self.result.message = f"Firmware differs for {len(mismatches)} component(s)"
            return
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Firmware versions match across {len(targets)} targets"
