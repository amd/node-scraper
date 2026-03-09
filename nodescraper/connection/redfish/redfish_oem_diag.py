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
"""
OEM diagnostic log collection via Redfish API.

Uses the same HTTP library as RedfishConnection (requests). Flow:
1. POST LogService.CollectDiagnosticData with OEM type
2. Poll task monitor until completion
3. GET task result, then LogEntry, then download AdditionalDataURI
4. Save log archive and metadata to the filesystem
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator
from requests import Response
from requests.status_codes import codes

from .redfish_connection import RedfishConnection, RedfishConnectionError

# Redfish JSON key for resource link
RF_ODATA_ID = "@odata.id"

RF_ANNOTATION_ALLOWABLE = "OEMDiagnosticDataType@Redfish.AllowableValues"

# Default max wait for async task (seconds)
DEFAULT_TASK_TIMEOUT_S = 600


def get_oem_diagnostic_allowable_values(
    conn: RedfishConnection,
    log_service_path: str,
) -> Optional[list[str]]:
    """GET the LogService and return OEMDiagnosticDataType@Redfish.AllowableValues if present.

    Args:
        conn: Redfish connection (session established).
        log_service_path: Path to the LogService (e.g. redfish/v1/Systems/UBB/LogServices/DiagLogs).

    Returns:
        List of allowable type strings, or None if not found / GET failed.
    """
    path = log_service_path.strip().strip("/")
    try:
        data = conn.get(path)
    except RedfishConnectionError:
        return None
    if not isinstance(data, dict):
        return None
    allow = data.get(RF_ANNOTATION_ALLOWABLE)
    if isinstance(allow, list) and all(isinstance(x, str) for x in allow):
        return list(allow)
    actions = data.get("Actions") or {}
    collect_action = actions.get("LogService.CollectDiagnosticData") or actions.get(
        "#LogService.CollectDiagnosticData"
    )
    if isinstance(collect_action, dict):
        allow = collect_action.get(RF_ANNOTATION_ALLOWABLE)
        if isinstance(allow, list) and all(isinstance(x, str) for x in allow):
            return list(allow)
    return None


class RedfishOemDiagCollectorArgs(BaseModel):
    """Collector/analyzer args for Redfish OEM diagnostic log collection."""

    log_service_path: str = Field(
        default="redfish/v1/Systems/UBB/LogServices/DiagLogs",
        description="Redfish path to the LogService (e.g. DiagLogs).",
    )
    oem_diagnostic_types_allowable: Optional[list[str]] = Field(
        default=None,
        description="Allowable OEM diagnostic types for this architecture/BMC. When set, used for validation and as default for oem_diagnostic_types when empty.",
    )
    oem_diagnostic_types: list[str] = Field(
        default_factory=list,
        description="OEM diagnostic types to collect. When empty and oem_diagnostic_types_allowable is set, defaults to that list.",
    )
    task_timeout_s: int = Field(
        default=DEFAULT_TASK_TIMEOUT_S,
        ge=1,
        le=3600,
        description="Max seconds to wait for each async collection task.",
    )

    @model_validator(mode="after")
    def _default_oem_diagnostic_types(self) -> "RedfishOemDiagCollectorArgs":
        if not self.oem_diagnostic_types and self.oem_diagnostic_types_allowable:
            return self.model_copy(
                update={"oem_diagnostic_types": list(self.oem_diagnostic_types_allowable)}
            )
        return self


def _resolve_path(conn: RedfishConnection, path: str) -> str:
    """Return full URL for a path (relative to base_url)."""
    if path.startswith("http"):
        return path
    path = path.lstrip("/")
    base = conn.base_url.rstrip("/")
    return f"{base}/{path}"


def _get_path_from_connection(conn: RedfishConnection, path: str) -> str:
    """Return path relative to BMC (no host). For use with conn.get_response(path)."""
    if path.startswith("http"):
        # Strip base URL to get path under /redfish/v1/...
        base = conn.base_url.rstrip("/")
        if path.startswith(base + "/"):
            return path[len(base) :].lstrip("/")
        return path
    return path.lstrip("/")


def collect_oem_diagnostic_data(
    conn: RedfishConnection,
    log_service_path: str,
    oem_diagnostic_type: str = "JournalControl",
    task_timeout_s: int = DEFAULT_TASK_TIMEOUT_S,
    output_dir: Optional[Path] = None,
    validate_type: bool = False,
    allowed_types: Optional[list[str]] = None,
) -> tuple[Optional[bytes], Optional[dict[str, Any]], Optional[str]]:
    """
    Initiate OEM diagnostic collection, poll until done, download log and metadata.

    Uses RedfishConnection (requests) only; no urllib3 or other HTTP libs.

    Args:
        conn: Redfish connection (session already established).
        log_service_path: Path to LogService under Systems, e.g.
            "redfish/v1/Systems/UBB/LogServices/DiagLogs" (no leading slash).
        oem_diagnostic_type: OEM type for DiagnosticDataType OEM (e.g. "JournalControl", "AllLogs").
        task_timeout_s: Max seconds to wait for async task.
        output_dir: If set, save log archive and LogEntry JSON here.
        validate_type: If True, require oem_diagnostic_type to be in allowed_types (or fallback).
        allowed_types: Allowable OEM diagnostic types for validation when validate_type is True.
            Set from collector args (oem_diagnostic_types_allowable) per architecture.

    Returns:
        (log_bytes, log_entry_metadata_dict, error_message).
        On success: (bytes, dict, None). On failure: (None, None, error_str).
    """
    if validate_type and allowed_types and oem_diagnostic_type not in allowed_types:
        return (
            None,
            None,
            f"oem_diagnostic_type {oem_diagnostic_type!r} not in allowed types",
        )
    path_prefix = log_service_path.rstrip("/")
    action_path = f"{path_prefix}/Actions/LogService.CollectDiagnosticData"
    payload = {"DiagnosticDataType": "OEM", "OEMDiagnosticDataType": oem_diagnostic_type}

    try:
        resp: Response = conn.post(action_path, json=payload)
    except RedfishConnectionError as e:
        return None, None, str(e)

    if resp.status_code != codes.accepted:
        return (
            None,
            None,
            f"Unexpected status {resp.status_code} for CollectDiagnosticData: {resp.text}",
        )

    task_monitor = resp.headers.get("Location")
    if task_monitor and not task_monitor.startswith("http"):
        task_monitor = _resolve_path(conn, task_monitor)
    sleep_s = int(resp.headers.get("Retry-After", 1) or 1)
    oem_response = resp.json()

    # AMD/Supermicro workaround: some BMCs omit Location; get TaskMonitor from body
    if not task_monitor:
        task_monitor_odata = oem_response.get(RF_ODATA_ID)
        if task_monitor_odata:
            task_path = _get_path_from_connection(conn, task_monitor_odata)
            task_resp = conn.get_response(task_path)
            if task_resp.status_code == codes.ok:
                task_monitor = task_resp.json().get("TaskMonitor")
                if task_monitor and not task_monitor.startswith("http"):
                    task_monitor = _resolve_path(conn, task_monitor)
        if not task_monitor:
            return None, None, "No TaskMonitor in response and no Location header"

    # Poll task monitor until no longer 202/404
    start = time.time()
    while True:
        if time.time() - start > task_timeout_s:
            return None, None, f"Task did not complete within {task_timeout_s}s"
        time.sleep(sleep_s)
        monitor_path = _get_path_from_connection(conn, task_monitor)
        poll_resp = conn.get_response(monitor_path)
        if poll_resp.status_code not in (codes.accepted, codes.not_found):
            break

    # Task resource URI: remove /Monitor suffix
    task_uri = task_monitor.rstrip("/")
    if task_uri.endswith("/Monitor"):
        task_uri = task_uri[: -len("/Monitor")]
    task_path = _get_path_from_connection(conn, task_uri)
    task_resp = conn.get_response(task_path)
    if task_resp.status_code != codes.ok:
        return None, None, f"Task GET failed: {task_resp.status_code}"
    task_json = task_resp.json()
    if task_json.get("TaskState") != "Completed":
        return None, None, f"Task did not complete: TaskState={task_json.get('TaskState')}"

    # LogEntry location from Payload.HttpHeaders
    headers_list = task_json.get("Payload", {}).get("HttpHeaders", []) or []
    location = None
    for header in headers_list:
        if isinstance(header, str) and "Location:" in header:
            location = header.split("Location:", 1)[-1].strip()
            break
    if not location:
        return None, None, "Location header missing in task Payload.HttpHeaders"
    if location.startswith("http"):
        location = _get_path_from_connection(conn, location)
    else:
        location = location.lstrip("/")

    # GET LogEntry resource
    log_entry_resp = conn.get_response(location)
    if log_entry_resp.status_code != codes.ok:
        return None, None, f"LogEntry GET failed: {log_entry_resp.status_code}"
    log_entry_json = log_entry_resp.json()

    # Download binary log if AdditionalDataURI present
    log_bytes: Optional[bytes] = None
    data_uri = log_entry_json.get("AdditionalDataURI")
    if data_uri:
        data_path = _get_path_from_connection(conn, data_uri)
        data_resp = conn.get_response(data_path)
        if data_resp.status_code == codes.ok:
            log_bytes = data_resp.content

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if log_bytes is not None:
            (output_dir / f"{oem_diagnostic_type}.tar.xz").write_bytes(log_bytes)
        metadata_file = output_dir / f"{oem_diagnostic_type}_log_entry.json"
        try:
            metadata_file.write_text(json.dumps(log_entry_json, indent=2), encoding="utf-8")
        except Exception:
            pass

    return log_bytes, log_entry_json, None
