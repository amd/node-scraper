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
from nodescraper.enums import ExecutionStatus
from nodescraper.models import CollectorArgs, DataPluginResult, PluginResult, TaskResult

from .analyzer_args import ServiceabilityAnalyzerArgs
from .se_runner import HubRunError, preflight_afid_sag, preflight_module_hub
from .serviceability_collector import ServiceabilityCollectorBase
from .serviceability_data import ServiceabilityDataModel


class ServiceabilityPluginBase(
    OOBandDataPlugin[
        ServiceabilityDataModel,
        CollectorArgs,
        ServiceabilityAnalyzerArgs,
    ],
):
    """OOB Redfish plugin stub; subclass with a concrete COLLECTOR and COLLECTOR_ARGS."""

    DATA_MODEL = ServiceabilityDataModel
    COLLECTOR = ServiceabilityCollectorBase
    COLLECTOR_ARGS = CollectorArgs
    ANALYZER_ARGS = ServiceabilityAnalyzerArgs

    def _apply_afid_sag_path_to_collection_args(
        self,
        afid_sag_path: str,
        collection_args: Any,
    ) -> Any:
        """Copy a resolved AFID_SAG path onto collector args when the collector stores one.

        Args:
            afid_sag_path: Absolute path returned by preflight.
            collection_args: Collector args for this run, or None.

        Returns:
            Collector args unchanged. Subclasses that store the path override this.
        """
        return collection_args

    def _plugin_error_result(self, message: str) -> PluginResult:
        """Build a plugin result that skips collection and fails analysis.

        Args:
            message: Error recorded on the plugin and analysis results.

        Returns:
            Plugin result with collection NOT_RAN and analysis ERROR.
        """
        self.logger.error("(%s) %s", self.__class__.__name__, message)
        return PluginResult(
            status=ExecutionStatus.ERROR,
            source=self.__class__.__name__,
            message=message,
            result_data=DataPluginResult(
                collection_result=TaskResult(
                    status=ExecutionStatus.NOT_RAN,
                    parent=self.__class__.__name__,
                    message="Data collection skipped",
                ),
                analysis_result=TaskResult(
                    status=ExecutionStatus.ERROR,
                    parent=self.__class__.__name__,
                    message=message,
                ),
            ),
        )

    def _preflight_hub_sag(
        self,
        collection_args: Any,
        analysis_args: Optional[Union[ServiceabilityAnalyzerArgs, dict[str, Any]]],
    ) -> Union[
        tuple[Any, Optional[Union[ServiceabilityAnalyzerArgs, dict[str, Any]]]],
        PluginResult,
    ]:
        """Resolve and validate AFID_SAG before collection when an entry-point hub will run.

        Args:
            collection_args: Collector args for this run, or None.
            analysis_args: Analyzer args for this run, or None.

        Returns:
            Updated collector and analyzer args, or a plugin error when preflight fails.
        """
        try:
            parsed = (
                analysis_args
                if isinstance(analysis_args, self.ANALYZER_ARGS)
                else self.ANALYZER_ARGS(**(analysis_args or {}))
            )
            if parsed.skip_hub:
                return collection_args, analysis_args
            if not parsed.uses_entry_point_hub():
                preflight_module_hub(parsed, self.logger)
                return collection_args, analysis_args
            sag_path = preflight_afid_sag(parsed, self.logger)
        except (HubRunError, ValueError) as exc:
            return self._plugin_error_result(f"AFID_SAG preflight failed: {exc}")
        if isinstance(analysis_args, dict):
            updated_analysis: Optional[Union[ServiceabilityAnalyzerArgs, dict[str, Any]]] = {
                **analysis_args,
                "afid_sag_path": sag_path,
            }
        elif analysis_args is None:
            updated_analysis = {"afid_sag_path": sag_path}
        else:
            updated_analysis = parsed.model_copy(update={"afid_sag_path": sag_path})
        return (
            self._apply_afid_sag_path_to_collection_args(sag_path, collection_args),
            updated_analysis,
        )
