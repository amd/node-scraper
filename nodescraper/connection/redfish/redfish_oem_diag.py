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

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from requests import Response
from requests.status_codes import codes

from nodescraper.enums import TaskState

from .redfish_connection import RedfishConnection, RedfishConnectionError
from .redfish_path import RedfishPath

_module_logger = logging.getLogger(__name__)

_LOG_RESPONSE_BODY_LIMIT = 1500


def _log_collect_diag_response(
    log: logging.Logger,
    status: int,
    body: Any,
    raw_text: str = "",
) -> None:
    """Log CollectDiagnosticData response at INFO when no Location/TaskMonitor found."""
    if isinstance(body, dict):
        snippet = json.dumps(body, indent=2)
    else:
        snippet = raw_text or str(body)
    if len(snippet) > _LOG_RESPONSE_BODY_LIMIT:
        snippet = snippet[:_LOG_RESPONSE_BODY_LIMIT] + "... (truncated)"
    log.info(
        "CollectDiagnosticData response (no Location/TaskMonitor): status=%s body=%s",
        status,
        snippet,
    )


# Redfish JSON key for resource link
RF_ODATA_ID = "@odata.id"

# @Redfish.AllowableValues: Redfish annotation for the list of allowable values for a string
REDFISH_ANNOTATION_ALLOWABLE_VALUES = "Redfish.AllowableValues"

# OEMDiagnosticDataType: LogService CollectDiagnosticData action parameter
OEM_DIAGNOSTIC_DATA_TYPE_PARAM = "OEMDiagnosticDataType"

RF_ANNOTATION_ALLOWABLE = f"{OEM_DIAGNOSTIC_DATA_TYPE_PARAM}@{REDFISH_ANNOTATION_ALLOWABLE_VALUES}"

# Default max wait for BMC task (seconds)
DEFAULT_TASK_TIMEOUT_S = 1800


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
        data = conn.get(RedfishPath(path))
    except RedfishConnectionError:
        return None
    if not isinstance(data, dict):
        return None
    actions = data.get("Actions") or {}
    collect_action = actions.get("LogService.CollectDiagnosticData") or actions.get(
        "#LogService.CollectDiagnosticData"
    )
    if isinstance(collect_action, dict):
        allow = collect_action.get(RF_ANNOTATION_ALLOWABLE)
        if isinstance(allow, list) and all(isinstance(x, str) for x in allow):
            return list(allow)
    return None


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


def _get_task_monitor_uri(body: dict, conn: RedfishConnection) -> Optional[str]:
    """Extract task monitor URI from a Task-like body (DSP0266 or OEM variants).

    TaskMonitor may be a string URI or an object with @odata.id (e.g. TaskService/TaskMonitors/378).
    """

    def _resolve_uri(uri: str) -> str:
        if not uri.startswith("http"):
            uri = _resolve_path(conn, uri.strip().lstrip("/"))
        return uri

    for key in ("TaskMonitor", "Monitor", "TaskMonitorUri"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return _resolve_uri(val)
        if isinstance(val, dict):
            odata_id = val.get(RF_ODATA_ID)
            if isinstance(odata_id, str) and odata_id.strip():
                return _resolve_uri(odata_id)
    oem = body.get("Oem")
    if isinstance(oem, dict):
        for vendor_dict in oem.values():
            if isinstance(vendor_dict, dict):
                for k in ("TaskMonitor", "Monitor", "TaskMonitorUri"):
                    val = vendor_dict.get(k)
                    if isinstance(val, str) and val.strip():
                        return _resolve_uri(val)
                    if isinstance(val, dict):
                        odata_id = val.get(RF_ODATA_ID)
                        if isinstance(odata_id, str) and odata_id.strip():
                            return _resolve_uri(odata_id)
    return None


# Workaround for LogEntry URL: some BMCs 404 when URL includes port
def _strip_port_from_url(url: str) -> Optional[str]:
    """Return URL with port removed from authority (e.g. host:443 -> host)."""
    if re.search(r"://[^/]+:\d+", url):
        return re.sub(r"(://[^:/]+):\d+", r"\1", url, count=1)
    return None


def _download_log_and_save(
    conn: RedfishConnection,
    log_entry_json: dict[str, Any],
    oem_diagnostic_type: str,
    output_dir: Optional[Path],
    log: logging.Logger,
) -> Optional[bytes]:
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
            archive_path = output_dir / f"{oem_diagnostic_type}.tar.xz"
            archive_path.write_bytes(log_bytes)
            log.info("Log written to disk: %s -> %s", oem_diagnostic_type, archive_path.name)
        metadata_file = output_dir / f"{oem_diagnostic_type}_log_entry.json"
        try:
            metadata_file.write_text(json.dumps(log_entry_json, indent=2), encoding="utf-8")
            log.info(
                "Log metadata written to disk: %s -> %s", oem_diagnostic_type, metadata_file.name
            )
        except Exception as e:
            log.exception("Failed to write log metadata to %s: %s", metadata_file, e)

    return log_bytes


def collect_oem_diagnostic_data(
    conn: RedfishConnection,
    log_service_path: str,
    oem_diagnostic_type: Optional[str] = None,
    task_timeout_s: int = DEFAULT_TASK_TIMEOUT_S,
    output_dir: Optional[Path] = None,
    validate_type: bool = False,
    allowed_types: Optional[list[str]] = None,
    logger: Optional[logging.Logger] = None,
) -> tuple[Optional[bytes], Optional[dict[str, Any]], Optional[str]]:
    """
    Initiate OEM diagnostic collection, poll until done, download log and metadata.

    Args:
        conn: Redfish connection (session already established).
        log_service_path: Path to LogService under Systems, e.g.
            "redfish/v1/Systems/UBB/LogServices/DiagLogs" (no leading slash).
        oem_diagnostic_type: OEM type for DiagnosticDataType OEM (e.g. "JournalControl", "AllLogs"). Required.
        task_timeout_s: Max seconds to wait for BMC task
        output_dir: If set, save log archive and LogEntry JSON here.
        validate_type: If True, require oem_diagnostic_type to be in allowed_types.
        allowed_types: Allowable OEM diagnostic types for validation when validate_type is True.
        logger: Logger

    Returns:
        (log_bytes, log_entry_metadata_dict, error_message).
        On success: (bytes, dict, None). On failure: (None, None, error_str).
    """
    log = logger if logger is not None else _module_logger
    if not oem_diagnostic_type or not oem_diagnostic_type.strip():
        return None, None, "oem_diagnostic_type is required"
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

    if resp.status_code not in (codes.ok, codes.accepted):
        return (
            None,
            None,
            f"Unexpected status {resp.status_code} for CollectDiagnosticData: {resp.text}",
        )

    # DSP0266 12.2: 202 shall include Location (task monitor URI), optionally Retry-After
    location_header = resp.headers.get("Location") or resp.headers.get("Content-Location")
    if location_header and not location_header.startswith("http"):
        location_header = _resolve_path(conn, location_header)
    sleep_s = int(resp.headers.get("Retry-After", 1) or 1)
    try:
        oem_response = resp.json()
    except Exception:
        oem_response = {}

    # 200 OK with TaskState=Completed: synchronous completion, body is the Task
    task_json: Optional[dict[str, Any]] = None
    if resp.status_code == codes.ok and isinstance(oem_response, dict):
        if oem_response.get("TaskState") == TaskState.completed.value:
            headers_list = oem_response.get("Payload", {}).get("HttpHeaders", []) or []
            if any(isinstance(h, str) and "Location:" in h for h in headers_list):
                task_json = oem_response

    # When TaskMonitor is implemented
    task_monitor: Optional[str] = None
    task_path: Optional[str] = None
    if task_json is None:
        task_monitor = location_header or _get_task_monitor_uri(oem_response, conn)
        if oem_response.get(RF_ODATA_ID):
            task_path = _get_path_from_connection(conn, oem_response[RF_ODATA_ID])
        if not task_monitor and task_path:
            task_resp = conn.get_response(task_path)
            if task_resp.status_code == codes.ok:
                fetched = task_resp.json()
                task_monitor = _get_task_monitor_uri(fetched, conn)
        if not task_monitor:
            _log_collect_diag_response(
                log, resp.status_code, oem_response, getattr(resp, "text", "") or ""
            )
            return None, None, "No TaskMonitor in response and no Location header"

    if task_json is None:
        assert task_monitor is not None
        # Poll task monitor until no longer 202/404 (e.g. GET /redfish/v1/TaskService/TaskMonitors/378)
        start = time.time()
        poll_resp = None
        while True:
            if time.time() - start > task_timeout_s:
                return None, None, f"Task did not complete within {task_timeout_s}s"
            time.sleep(sleep_s)
            monitor_path = _get_path_from_connection(conn, task_monitor)
            poll_resp = conn.get_response(monitor_path)
            if poll_resp.status_code not in (codes.accepted, codes.not_found):
                break

        # TaskMonitor response body has @odata.id pointing to the Task (e.g. /redfish/v1/TaskService/Tasks/5)
        try:
            monitor_body = poll_resp.json() if poll_resp else {}
        except Exception:
            monitor_body = {}
        task_uri_from_monitor = (
            monitor_body.get(RF_ODATA_ID) if isinstance(monitor_body, dict) else None
        )
        if isinstance(task_uri_from_monitor, str) and task_uri_from_monitor.strip():
            task_path = _get_path_from_connection(conn, task_uri_from_monitor.strip())
        elif not task_path:
            task_path = _get_path_from_connection(conn, task_monitor.rstrip("/").rsplit("/", 1)[0])
        task_resp = conn.get_response(task_path)
        if task_resp.status_code != codes.ok:
            return None, None, f"Task GET failed: {task_resp.status_code}"
        task_json = task_resp.json()
        if task_json.get("TaskState") != TaskState.completed.value:
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
        log_entry_path = location
    else:
        log_entry_path = location.lstrip("/")

    # GET LogEntry (some BMCs 404 when URL includes explicit port; try without port first)
    log_entry_alt = _strip_port_from_url(log_entry_path)
    if log_entry_alt is None and not log_entry_path.startswith("http"):
        log_entry_alt = _strip_port_from_url(
            conn.base_url.rstrip("/") + "/" + log_entry_path.lstrip("/")
        )
    paths_to_try = [log_entry_alt, log_entry_path] if log_entry_alt else [log_entry_path]
    log_entry_json = None
    first_status: Optional[int] = codes.not_found
    first_error = ""
    for try_path in paths_to_try:
        if try_path is None:
            continue
        try:
            log_entry_resp = conn.get_response(try_path)
            if log_entry_resp.status_code == codes.ok:
                log_entry_json = log_entry_resp.json()
                break
            if try_path == paths_to_try[0]:
                first_status = log_entry_resp.status_code
        except Exception as e:
            if try_path == paths_to_try[0]:
                first_status = None
                first_error = str(e)
            continue
    if log_entry_json is None:
        err = first_error if first_status is None else f"status {first_status}"
        return None, None, f"LogEntry GET failed: {err} (GET {log_entry_path})"

    log_bytes = _download_log_and_save(conn, log_entry_json, oem_diagnostic_type, output_dir, log)
    return log_bytes, log_entry_json, None
