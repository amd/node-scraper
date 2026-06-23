###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, distribute, sublicense, and/or sell
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

from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.plugins.serviceability.afid_events import build_afid_events_from_data
from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs
from nodescraper.plugins.serviceability.cper_decode import (
    CperDecodeError,
    decode_cper_raw_attachments,
)
from nodescraper.plugins.serviceability.se_adapter import (
    format_serviceability_solution_lines,
)
from nodescraper.plugins.serviceability.se_models import ServiceabilityBlock
from nodescraper.plugins.serviceability.se_runner import SeRunError, run_service_hub
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)

from .mi3xx_cper_utils import CPER_METHOD_AFID_MAX, should_skip_cper_fetch_or_decode


class AfidSagMetadataArtifact(BaseModel):
    """Hub AFID_SAG metadata snapshot; written to ``afid_sag_metadata.json``."""

    ARTIFACT_LOG_BASENAME: ClassVar[str] = "afid_sag_metadata"

    metadata: dict[str, Any] = Field(default_factory=dict)


class MI3XXAnalyzer(DataAnalyzer[ServiceabilityDataModel, ServiceabilityAnalyzerArgs]):
    """Build AFID events from collected data and run the configured service hub."""

    DATA_MODEL = ServiceabilityDataModel

    def analyze_data(
        self,
        data: ServiceabilityDataModel,
        args: Optional[ServiceabilityAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "ServiceabilityAnalyzerArgs are required"
            return self.result

        events = data.afid_events or build_afid_events_from_data(data)
        data.afid_events = events

        if args.skip_hub:
            data.serviceability = ServiceabilityBlock(afid_events=events)
            self.result.status = ExecutionStatus.OK
            self.result.message = f"Built {len(events)} AFID event(s); hub skipped"
            self._log_serviceability_solutions(data.serviceability)
            return self.result

        parent = self.parent or self.__class__.__name__
        cper_data = data.cper_data or {}
        cper_raw_to_decode = self._cper_raw_needing_decode(data)
        skipped_cper = len(data.cper_raw or {}) - len(cper_raw_to_decode)
        if skipped_cper:
            self.logger.info(
                "(%s) Skipping CPER decode for %d CPER attachment(s); Redfish log "
                "already has usable ACA fields (CPER-method AFID<=%s or no serial on decode)",
                parent,
                skipped_cper,
                CPER_METHOD_AFID_MAX,
            )
        if cper_raw_to_decode and not cper_data:
            if not args.cper_decode_module:
                self.logger.warning(
                    "(%s) %d CPER attachment(s) collected but cper_decode_module is "
                    "not set in analysis_args; skipping CPER decode",
                    parent,
                    len(cper_raw_to_decode),
                )
            else:
                self.logger.info(
                    "(%s) Decoding %d CPER attachment(s) via %s.%s",
                    parent,
                    len(cper_raw_to_decode),
                    args.cper_decode_module,
                    args.cper_decode_method,
                )
                try:
                    cper_data = decode_cper_raw_attachments(
                        cper_raw_to_decode,
                        cper_decode_module=args.cper_decode_module,
                        cper_decode_method=args.cper_decode_method,
                        logger=self.logger,
                    )
                    data.cper_data = cper_data
                    self.logger.info(
                        "(%s) CPER decode finished: %d of %d attachment(s) decoded",
                        parent,
                        len(cper_data),
                        len(cper_raw_to_decode),
                    )
                except CperDecodeError as exc:
                    self.logger.warning(
                        "(%s) %s; continuing without decoded CPER",
                        parent,
                        exc,
                    )
        elif cper_data:
            self.logger.info(
                "(%s) Using %d pre-decoded CPER record(s) from collection",
                parent,
                len(cper_data),
            )

        try:
            block = run_service_hub(
                hub_python_module=args.hub_python_module,  # type: ignore[arg-type]
                hub_display_name=args.hub_display_name,
                afid_events=events,
                afid_sag_path=args.afid_sag_path,  # type: ignore[arg-type]
                rf_events=data.rf_events,
                cper_data=cper_data or None,
                hub_options=args.resolved_hub_options(),
                hub_analyze_method=args.hub_analyze_method,
                hub_init_path_kwarg=args.hub_init_path_kwarg,
            )
        except (SeRunError, ValueError) as exc:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = str(exc)
            return self.result

        data.serviceability = block
        self._append_afid_sag_metadata_artifact(block)
        self._log_serviceability_solutions(block)
        hub_label = args.hub_display_name or args.hub_python_module
        self.result.status = ExecutionStatus.OK
        cper_summary = ""
        if cper_data:
            cper_summary = f", {len(cper_data)} decoded CPER(s)"
        elif cper_raw_to_decode:
            cper_summary = f", {len(cper_raw_to_decode)} CPER attachment(s) not decoded"
        elif data.cper_raw:
            cper_summary = f", {len(data.cper_raw)} CPER attachment(s) omitted (ACA on log entry)"
        ver_bits: list[str] = []
        if block.hub_version:
            ver_bits.append(f"hub {block.hub_version}")
        if block.afid_sag_file_version:
            ver_bits.append(f"AFID_SAG {block.afid_sag_file_version}")
        ver_suffix = f" [{'; '.join(ver_bits)}]" if ver_bits else ""
        self.result.message = (
            f"{hub_label}: {len(block.solution)} solution(s) "
            f"from {len(data.rf_events)} Redfish event(s){cper_summary}{ver_suffix}"
        )
        return self.result

    @staticmethod
    def _cper_raw_needing_decode(data: ServiceabilityDataModel) -> dict[str, str]:
        """Subset of ``cper_raw`` that still needs configured CPER decode (not already on the log)."""
        raw = data.cper_raw or {}
        if not raw:
            return {}
        by_id: dict[str, dict[str, Any]] = {}
        for member in data.rf_events:
            if not isinstance(member, dict):
                continue
            eid = member.get("Id")
            if eid is not None:
                by_id[str(eid)] = member
        out: dict[str, str] = {}
        for event_id, blob in raw.items():
            ev = by_id.get(str(event_id))
            if ev is not None and should_skip_cper_fetch_or_decode(ev):
                continue
            out[str(event_id)] = blob
        return out

    def _append_afid_sag_metadata_artifact(self, block: ServiceabilityBlock) -> None:
        if block.afid_sag_metadata is None:
            return
        self.result.artifacts.append(
            AfidSagMetadataArtifact(metadata=dict(block.afid_sag_metadata))
        )

    def _log_serviceability_solutions(self, block: ServiceabilityBlock) -> None:
        parent = self.parent or self.__class__.__name__
        for line in format_serviceability_solution_lines(block):
            self.logger.info("(%s) %s", parent, line)
