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
"""Shared serviceability analysis path for on-demand plugins and the event daemon."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .afid_events import build_afid_events_from_data
from .analyzer_args import ServiceabilityAnalyzerArgs
from .cper_decode import CperDecodeError, decode_cper_raw_attachments
from .se_models import AfidEvent, ServiceabilityBlock
from .se_runner import HubRunError, run_entry_point_hub, run_service_hub
from .serviceability_data import ServiceabilityDataModel


@dataclass
class ServiceabilityWindowResult:
    """Outcome of analyze_serviceability_window for CLI plugins or the event daemon."""

    ok: bool
    message: str
    afid_events: list[AfidEvent]
    serviceability: Optional[ServiceabilityBlock] = None
    error: Optional[str] = None


def _cper_raw_needing_decode(data: ServiceabilityDataModel) -> dict[str, str]:
    """Return CPER attachments that still need configured decode."""
    from .mi3xx.mi3xx_cper_utils import should_skip_cper_fetch_or_decode

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


def analyze_serviceability_window(
    data: ServiceabilityDataModel,
    args: ServiceabilityAnalyzerArgs,
    *,
    logger: Optional[logging.Logger] = None,
    parent: str = "analyze_serviceability_window",
) -> ServiceabilityWindowResult:
    """Build AFID events and optionally run the configured service hub on rf_events."""
    log = logger or logging.getLogger(__name__)
    events = data.afid_events or build_afid_events_from_data(data)
    data.afid_events = events

    if args.skip_hub:
        if args.afid_sag_path and str(args.afid_sag_path).strip():
            data.afid_sag_path = str(args.afid_sag_path).strip()
        block = ServiceabilityBlock(afid_events=events)
        data.serviceability = block
        return ServiceabilityWindowResult(
            ok=True,
            message=f"Built {len(events)} AFID event(s); hub skipped",
            afid_events=events,
            serviceability=block,
        )

    cper_data = data.cper_data or {}
    cper_raw_to_decode = _cper_raw_needing_decode(data)
    skipped_cper = len(data.cper_raw or {}) - len(cper_raw_to_decode)
    if skipped_cper:
        from .mi3xx.mi3xx_cper_utils import CPER_METHOD_AFID_MAX

        log.info(
            "(%s) Skipping CPER decode for %d CPER attachment(s); Redfish log "
            "already has usable ACA fields (CPER-method AFID<=%s or no serial on decode)",
            parent,
            skipped_cper,
            CPER_METHOD_AFID_MAX,
        )
    if cper_raw_to_decode and not cper_data:
        if not args.cper_decode_module:
            log.warning(
                "(%s) %d CPER attachment(s) collected but cper_decode_module is "
                "not set in analysis_args; skipping CPER decode",
                parent,
                len(cper_raw_to_decode),
            )
        else:
            log.info(
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
                    logger=log,
                )
                data.cper_data = cper_data
                log.info(
                    "(%s) CPER decode finished: %d of %d attachment(s) decoded",
                    parent,
                    len(cper_data),
                    len(cper_raw_to_decode),
                )
            except CperDecodeError as exc:
                log.warning("(%s) %s; continuing without decoded CPER", parent, exc)
    elif cper_data:
        log.info(
            "(%s) Using %d pre-decoded CPER record(s) from collection",
            parent,
            len(cper_data),
        )

    if args.uses_entry_point_hub() and cper_data:
        events = build_afid_events_from_data(data)
        data.afid_events = events

    if args.uses_entry_point_hub() and not events:
        return ServiceabilityWindowResult(
            ok=False,
            message="No AFID events could be built from collected Redfish data",
            afid_events=events,
            error="empty afid_events",
        )

    sag_path = args.resolved_afid_sag_path()
    data.afid_sag_path = sag_path
    log.info(
        "(%s) Using AFID_SAG file: %s",
        parent,
        Path(sag_path).expanduser().resolve(),
    )
    try:
        if args.uses_module_hub():
            block = run_service_hub(
                hub_python_module=args.hub_python_module,  # type: ignore[arg-type]
                hub_display_name=args.hub_display_name,
                afid_events=events,
                afid_sag_path=sag_path,
                rf_events=data.rf_events,
                cper_data=cper_data or None,
                hub_options=args.resolved_hub_options(),
                hub_analyze_method=args.hub_analyze_method,
                hub_init_path_kwarg=args.hub_init_path_kwarg,
            )
        else:
            block = run_entry_point_hub(
                hub_entry_point=args.hub_entry_point,  # type: ignore[arg-type]
                hub_display_name=args.hub_display_name,
                afid_events=events,
                afid_sag_path=sag_path,
                rf_event_count=len(data.rf_events),
            )
    except (HubRunError, ValueError) as exc:
        return ServiceabilityWindowResult(
            ok=False,
            message=str(exc),
            afid_events=events,
            error=str(exc),
        )

    data.serviceability = block
    hub_label = args.hub_display_name or args.hub_python_module or args.hub_entry_point
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
    message = (
        f"{hub_label}: {len(block.solution)} solution(s) "
        f"from {len(data.rf_events)} Redfish event(s){cper_summary}{ver_suffix}"
    )
    return ServiceabilityWindowResult(
        ok=True,
        message=message,
        afid_events=events,
        serviceability=block,
    )
