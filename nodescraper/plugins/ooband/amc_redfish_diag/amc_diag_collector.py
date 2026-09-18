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
from pathlib import Path
from typing import Any, Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import collect_oem_diagnostic_data
from nodescraper.connection.redfish.redfish_constants import RF_MEMBERS, RF_ODATA_ID
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult
from nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_data import (
    OemDiagTypeResult,
    RedfishOemDiagDataModel,
)
from nodescraper.utils import pascal_to_snake

from .collector_args import AmcDiagCollectionSpec, AmcRedfishDiagCollectorArgs

_COLLECT_ACTION_KEYS = (
    "LogService.CollectDiagnosticData",
    "#LogService.CollectDiagnosticData",
)


def _collection_key(spec: AmcDiagCollectionSpec) -> str:
    """Build a stable results-dict key for one CollectDiagnosticData job.

    Args:
        spec: Collection request.

    Returns:
        Root, diagnostic type, and optional OEM type joined by colons.
    """
    if spec.oem_data_type:
        return f"{spec.root}:{spec.diagnostic_data_type}:{spec.oem_data_type}"
    return f"{spec.root}:{spec.diagnostic_data_type}"


class AmcRedfishDiagCollector(
    RedfishDataCollector[RedfishOemDiagDataModel, AmcRedfishDiagCollectorArgs]
):
    """Collect AMC Manager and Systems diagnostic bundles through SSH-proxy Redfish."""

    DATA_MODEL = RedfishOemDiagDataModel

    DOCUMENTATION_COLLECTION_ITEMS: tuple[str, ...] = (
        "SSH-proxy Redfish GET of Managers/Systems LogServices that advertise CollectDiagnosticData.",
        "CollectDiagnosticData for each collection_args.collections entry (Manager dump and OEM AllLogs by default).",
        "Optional binary archives under the plugin log path when log_path is set.",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log_path = kwargs.pop("log_path", None)
        super().__init__(*args, **kwargs)

    def collect_data(
        self, args: Optional[AmcRedfishDiagCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishOemDiagDataModel]]:
        """Discover AMC log services and run CollectDiagnosticData jobs.

        Args:
            args: Collection args. Defaults to the AMC manager dump plus systems AllLogs.

        Returns:
            TaskResult and RedfishOemDiagDataModel keyed by collection spec.
        """
        if args is None:
            args = AmcRedfishDiagCollectorArgs()
        jobs = list(args.collections) if args.collections else []
        if not jobs:
            self.result.message = "No AMC diagnostic collections configured"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        if self.log_path:
            output_dir = (
                Path(self.log_path)
                / pascal_to_snake(self.parent or "")
                / pascal_to_snake(self.__class__.__name__)
                / "diag_logs"
            ).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(
                "(AmcRedfishDiagPlugin) Diagnostic archives will be written to: %s",
                output_dir,
            )
        else:
            output_dir = None

        results: dict[str, OemDiagTypeResult] = {}
        for spec in jobs:
            key = _collection_key(spec)
            log_service = self._find_log_service(spec.root, args)
            if not log_service:
                missing_err = f"No CollectDiagnosticData LogService under {spec.root}"
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"AMC diag {key}: {missing_err}",
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                results[key] = OemDiagTypeResult(success=False, error=missing_err, metadata=None)
                continue
            _log_bytes, metadata, collect_err = collect_oem_diagnostic_data(
                self.connection,
                log_service_path=log_service,
                oem_diagnostic_type=spec.oem_data_type or None,
                diagnostic_data_type=spec.diagnostic_data_type,
                task_timeout_s=args.task_timeout_s,
                output_dir=output_dir,
                logger=self.logger,
            )
            if collect_err:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"AMC diag {key}: {collect_err}",
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                results[key] = OemDiagTypeResult(success=False, error=collect_err, metadata=None)
            else:
                results[key] = OemDiagTypeResult(success=True, error=None, metadata=metadata)

        success_count = sum(1 for r in results.values() if r.success)
        self.result.message = f"AMC diag: {success_count}/{len(results)} collections succeeded"
        self.result.status = ExecutionStatus.OK if success_count else ExecutionStatus.ERROR
        return self.result, RedfishOemDiagDataModel(results=results)

    def _member_paths(self, root: str, args: AmcRedfishDiagCollectorArgs) -> list[str]:
        """Resolve Systems or Managers member URIs to probe.

        Args:
            root: Managers or Systems.
            args: Collection args with optional member Ids.

        Returns:
            Redfish paths without a leading slash.
        """
        api_root = (getattr(self.connection, "api_root", None) or "redfish/v1").strip("/")
        ids = args.manager_ids if root == "Managers" else args.system_ids
        if ids:
            return [f"{api_root}/{root}/{member_id}" for member_id in ids]
        listing = self._run_redfish_get(f"/{api_root}/{root}")
        if not listing.success or not listing.data:
            return []
        paths: list[str] = []
        for member in listing.data.get(RF_MEMBERS) or []:
            if not isinstance(member, dict):
                continue
            odata_id = member.get(RF_ODATA_ID)
            if isinstance(odata_id, str) and odata_id.strip():
                paths.append(odata_id.strip().lstrip("/"))
        return paths

    def _find_log_service(self, root: str, args: AmcRedfishDiagCollectorArgs) -> Optional[str]:
        """Find the first LogService under root that advertises CollectDiagnosticData.

        Args:
            root: Managers or Systems.
            args: Collection args with optional member Ids.

        Returns:
            LogService path, or None if none found.
        """
        for member_path in self._member_paths(root, args):
            ls_list = self._run_redfish_get(f"/{member_path}/LogServices")
            if not ls_list.success or not ls_list.data:
                continue
            for member in ls_list.data.get(RF_MEMBERS) or []:
                if not isinstance(member, dict):
                    continue
                odata_id = member.get(RF_ODATA_ID)
                if not isinstance(odata_id, str) or not odata_id.strip():
                    continue
                ls_path = odata_id.strip().lstrip("/")
                ls_body = self._run_redfish_get(f"/{ls_path}")
                if not ls_body.success or not ls_body.data:
                    continue
                actions = ls_body.data.get("Actions") or {}
                if any(key in actions for key in _COLLECT_ACTION_KEYS):
                    return ls_path
        return None
