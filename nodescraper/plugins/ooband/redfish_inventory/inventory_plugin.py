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
from typing import Any, Optional, Union

from nodescraper.base import OOBandDataPlugin
from nodescraper.connection.redfish import (
    RedfishSshProxyConnectionManager,
    collected_multi_target_data,
)
from nodescraper.enums import EventPriority
from nodescraper.models import TaskResult

from .analyzer_args import RedfishInventoryAnalyzerArgs
from .collector_args import RedfishInventoryCollectorArgs
from .inventory_analyzer import RedfishInventoryAnalyzer
from .inventory_collector import RedfishInventoryCollector
from .inventory_data import RedfishInventoryDataModel


class RedfishInventoryPlugin(
    OOBandDataPlugin[
        RedfishInventoryDataModel,
        RedfishInventoryCollectorArgs,
        RedfishInventoryAnalyzerArgs,
    ]
):
    """Collect portable BMC and SMC Redfish inventory over the native Redfish connection.

    BMC coverage is Chassis, Managers, Assembly, PowerSubsystem, FruDevices, telemetry
    metric reports, UpdateService, FirmwareInventory, and Systems. SMC coverage is
    ComputerSystem, Memory, Processors, and FirmwareInventory. Every area is enabled
    unless collection_args.enabled turns it off.
    Collection follows links the service publishes and does not apply product member expectations.
    When two or more targets connect, analysis compares FirmwareInventory across those
    targets. compare_firmware defaults to true. A different version or a member missing on
    a connected target logs an FW warning. AmcRedfishInventoryPlugin runs that comparison
    on its own targets.

    Keep these outside node-scraper core: IPMI, SSH commands and file capture, PLDM,
    manufacturing-tool access, vendor-only BMC actions, BIOS and diagnostic logs, CPLD,
    post codes, SOL, CPER, and product checks for chassis topology, ports, PCIe, sensors,
    certificates, and firmware integrity. Non-Redfish fallbacks stay with the product
    collector that owns them.
    """

    DATA_MODEL = RedfishInventoryDataModel
    COLLECTOR = RedfishInventoryCollector
    COLLECTOR_ARGS = RedfishInventoryCollectorArgs
    ANALYZER = RedfishInventoryAnalyzer
    ANALYZER_ARGS = RedfishInventoryAnalyzerArgs

    def analyze(
        self,
        max_event_priority_level: Optional[Union[EventPriority, str]] = EventPriority.CRITICAL,
        analysis_args: Optional[Union[RedfishInventoryAnalyzerArgs, dict]] = None,
        data: Optional[Any] = None,
    ) -> TaskResult:
        """Compare firmware once across every target this plugin collected.

        Args:
            max_event_priority_level: Priority limit for events.
            analysis_args: Analyzer arguments. Defaults to comparing firmware.
            data: Pre-collected inventory for a single-target run.

        Returns:
            TaskResult: WARNING when firmware differs across connected targets.
        """
        if data:
            self.data = data
        args = self._analysis_args(analysis_args)
        analyzer = RedfishInventoryAnalyzer(
            system_info=self.system_info.model_copy(),
            logger=self.logger,
            max_event_priority_level=max_event_priority_level or EventPriority.CRITICAL,
            parent=self.__class__.__name__,
            task_result_hooks=self.task_result_hooks,
            event_reporter=self.event_reporter,
            session_id=self.session_id,
        )
        self.analysis_result = analyzer.compare_firmware(self._firmware_targets(), args)
        return self.analysis_result

    def _analysis_args(
        self, analysis_args: Optional[Union[RedfishInventoryAnalyzerArgs, dict]]
    ) -> RedfishInventoryAnalyzerArgs:
        """Return analyzer args, applying the compare_firmware default when omitted.

        Args:
            analysis_args: Caller-supplied analyzer arguments.

        Returns:
            Validated analyzer arguments.
        """
        if analysis_args is None:
            return RedfishInventoryAnalyzerArgs()
        if isinstance(analysis_args, dict):
            return RedfishInventoryAnalyzerArgs.model_validate(analysis_args)
        return analysis_args

    def _firmware_targets(self) -> dict[str, RedfishInventoryDataModel]:
        """Return inventory models for the connected targets, or the single collected model.

        Args:
            None

        Returns:
            Target key to inventory model.
        """
        models: dict[str, RedfishInventoryDataModel] = {}
        for key, value in collected_multi_target_data(self.connection_manager).items():
            model = _as_inventory_model(value)
            if model is not None:
                models[str(key)] = model
        if models:
            return models
        model = _as_inventory_model(self.data)
        if model is None:
            return {}
        return {"target": model}


def _as_inventory_model(value: Any) -> Optional[RedfishInventoryDataModel]:
    """Return an inventory model when value is one or a dumped responses dict.

    Args:
        value: Collected data for one target.

    Returns:
        The inventory model, or None when value is not inventory.
    """
    if isinstance(value, RedfishInventoryDataModel):
        return value
    if isinstance(value, dict) and isinstance(value.get("responses"), dict):
        return RedfishInventoryDataModel.model_validate(value)
    return None


class AmcRedfishInventoryPlugin(RedfishInventoryPlugin):
    """Collect the same Redfish inventory through the BMC SSH proxy.

    Pair this with RedfishInventoryPlugin so one run reads the BMC on the direct
    Redfish connection and the AMC on RedfishSshProxyConnectionManager. collection_args
    and analysis_args are the same for both plugins. Firmware comparison uses only the
    targets this plugin connected.
    """

    CONNECTION_TYPE = RedfishSshProxyConnectionManager  # type: ignore[assignment]
