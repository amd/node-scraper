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
from __future__ import annotations

from typing import Annotated, Any, Optional, Union

from pydantic import Field

from nodescraper.enums import EventPriority, ExecutionStatus, SystemInteractionLevel
from nodescraper.models import DataPluginResult, PluginResult, TaskResult
from nodescraper.plugins.serviceability.afid_sag_lookup import log_afid_fru_summary
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataLoadError,
    ServiceabilityDataModel,
)
from nodescraper.plugins.serviceability.serviceability_hub_analyzer import (
    ServiceabilityHubAnalyzer,
)
from nodescraper.plugins.serviceability.serviceability_plugin_base import (
    ServiceabilityPluginBase,
)
from nodescraper.utils import register_log_dir_name

from .mi4xx_analyzer_args import Mi4xxServiceabilityAnalyzerArgs
from .mi4xx_collector import MI4XXCollector
from .mi4xx_collector_args import MI4XXCollectorArgs

register_log_dir_name("Mi4xxServiceabilityPlugin", "serviceability_plugin_mi4xx")
register_log_dir_name("MI4XXCollector", "mi4xx_collector")
register_log_dir_name("ServiceabilityHubAnalyzer", "serviceability_hub_analyzer")


class Mi4xxServiceabilityPlugin(ServiceabilityPluginBase):
    """MI4xx / Helios OOB Redfish serviceability via a registered hub entry point."""

    DATA_MODEL = ServiceabilityDataModel
    COLLECTOR = MI4XXCollector  # type: ignore[assignment]
    ANALYZER = ServiceabilityHubAnalyzer
    COLLECTOR_ARGS = MI4XXCollectorArgs
    ANALYZER_ARGS = Mi4xxServiceabilityAnalyzerArgs

    @staticmethod
    def _resolved_afid_sag_path(
        collection_args: Optional[Union[MI4XXCollectorArgs, dict[str, Any]]],
        analysis_args: Optional[Union[Mi4xxServiceabilityAnalyzerArgs, dict[str, Any]]],
    ) -> Optional[str]:
        if analysis_args is not None:
            if isinstance(analysis_args, dict):
                path = analysis_args.get("afid_sag_path")
                if path and str(path).strip():
                    return str(path).strip()
            else:
                return analysis_args.resolved_afid_sag_path()
        if collection_args is not None:
            if isinstance(collection_args, dict):
                path = collection_args.get("afid_sag_path")
                if path and str(path).strip():
                    return str(path).strip()
            else:
                return collection_args.resolved_afid_sag_path_for_collection()
        return None

    @staticmethod
    def _merge_mi4xx_collection_args(
        collection_args: Optional[Union[MI4XXCollectorArgs, dict[str, Any]]],
        analysis_args: Optional[Union[Mi4xxServiceabilityAnalyzerArgs, dict[str, Any]]],
    ) -> Optional[Union[MI4XXCollectorArgs, dict[str, Any]]]:
        if analysis_args is None:
            return collection_args
        if isinstance(analysis_args, dict):
            uri = analysis_args.get("rf_event_log_uri")
        else:
            uri = analysis_args.rf_event_log_uri
        if not uri or not str(uri).strip():
            return collection_args
        uri_text = str(uri).strip()
        if collection_args is None:
            return {"rf_event_log_uri": uri_text}
        if isinstance(collection_args, dict):
            if not str(collection_args.get("rf_event_log_uri") or "").strip():
                merged = dict(collection_args)
                merged["rf_event_log_uri"] = uri_text
                return merged
            return collection_args
        if "rf_event_log_uri" not in collection_args.model_fields_set:
            return collection_args.model_copy(update={"rf_event_log_uri": uri_text})
        return collection_args

    def _plugin_error_result(self, message: str) -> PluginResult:
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

    def run(  # type: ignore[override]
        self,
        collection: Annotated[
            bool,
            "Run the collector (True) or skip it (False).",
        ] = True,
        analysis: Annotated[
            bool,
            "Run the analyzer (True) or skip it (False).",
        ] = True,
        max_event_priority_level: Union[EventPriority, str] = EventPriority.CRITICAL,
        system_interaction_level: Annotated[
            Union[SystemInteractionLevel, str],
            "System interaction level (e.g. PASSIVE, INTERACTIVE, DISRUPTIVE).",
        ] = SystemInteractionLevel.INTERACTIVE,
        preserve_connection: bool = False,
        data: Annotated[
            Optional[Union[str, dict, ServiceabilityDataModel]],
            Field(
                description=(
                    "Path to pre-collected Redfish Entries JSON or ServiceabilityDataModel JSON; "
                    "use with --collection False to analyze offline without BMC collection."
                ),
            ),
        ] = None,
        collection_args: Optional[Union[MI4XXCollectorArgs, dict[str, Any]]] = None,
        analysis_args: Optional[Union[Mi4xxServiceabilityAnalyzerArgs, dict[str, Any]]] = None,
    ) -> PluginResult:
        if analysis and not collection and data is not None:
            try:
                loaded = (
                    data
                    if isinstance(data, ServiceabilityDataModel)
                    else self.DATA_MODEL.import_model(data)
                )
            except ServiceabilityDataLoadError as exc:
                return self._plugin_error_result(str(exc))
            member_count = len(loaded.rf_events)
            self.logger.info(
                "(%s) Loaded %d event log member(s) from --data (collection skipped)",
                self.__class__.__name__,
                member_count,
            )
            log_afid_fru_summary(
                self.logger,
                self.__class__.__name__,
                loaded,
                self._resolved_afid_sag_path(collection_args, analysis_args),
            )
            sag_path = self._resolved_afid_sag_path(collection_args, analysis_args)
            if sag_path:
                loaded.afid_sag_path = sag_path

        return super().run(
            collection=collection,
            analysis=analysis,
            max_event_priority_level=max_event_priority_level,
            system_interaction_level=system_interaction_level,
            preserve_connection=preserve_connection,
            data=data,
            collection_args=self._merge_mi4xx_collection_args(collection_args, analysis_args),
            analysis_args=analysis_args,
        )
