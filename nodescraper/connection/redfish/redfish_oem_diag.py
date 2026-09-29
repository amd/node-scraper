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

from requests.status_codes import codes

from nodescraper.enums import TaskState

from .redfish_connection import (
    RedfishConnection,
    RedfishConnectionError,
    RedfishHttpResponse,
)
from .redfish_constants import RF_ODATA_ID
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
    odata_id = body.get(RF_ODATA_ID)
    if isinstance(odata_id, str) and odata_id.strip():
        base_uri = _resolve_uri(odata_id)
        return f"{base_uri.rstrip('/')}/Monitor"
    return None


def _task_resource_path(path: str) -> Optional[str]:
    """Return a TaskService/Tasks path when path is a Task member, else None.

    Args:
        path: Absolute or relative Redfish URI.

    Returns:
        Normalized Task path, or None.
    """
    stripped = path.strip().lstrip("/")
    if "TaskService/Tasks/" in stripped and "TaskMonitors" not in stripped:
        return stripped
    return None


def _poll_task_resource(
    conn: RedfishConnection,
    task_path: str,
    timeout_s: int,
    sleep_s: int,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """GET a Task resource until TaskState is Completed or a terminal failure.

    Args:
        conn: Redfish connection.
        task_path: Path to a TaskService/Tasks member.
        timeout_s: Max seconds to wait.
        sleep_s: Seconds between GETs.

    Returns:
        (task JSON, None) on success, or (None, error).
    """
    start = time.time()
    interval = max(int(sleep_s), 1)
    while True:
        if time.time() - start > timeout_s:
            return None, f"Task did not complete within {timeout_s}s"
        poll_resp = conn.get_response(task_path)
        if poll_resp.status_code == codes.ok:
            try:
                body = poll_resp.json()
            except Exception:
                body = {}
            if isinstance(body, dict):
                state = body.get("TaskState")
                if state == TaskState.completed.value:
                    return body, None
                if state in (
                    TaskState.exception.value,
                    TaskState.cancelled.value,
                    TaskState.killed.value,
                ):
                    return None, f"Task did not complete: TaskState={state}"
        elif poll_resp.status_code != codes.accepted:
            return None, f"Task GET failed: {poll_resp.status_code}"
        time.sleep(interval)


# Workaround for LogEntry URL: some BMCs 404 when URL includes port
def _strip_port_from_url(url: str) -> Optional[str]:
    """Return URL with port removed from authority (e.g. host:443 -> host)."""
    if re.search(r"://[^/]+:\d+", url):
        return re.sub(r"(://[^:/]+):\d+", r"\1", url, count=1)
    return None


_LOG_ENTRY_GET_ATTEMPTS = 4
_LOG_ENTRY_GET_RETRY_SLEEP_S = 2


def _entries_collection_path(log_entry_path: str) -> Optional[str]:
    """Return the Entries collection path for a LogEntry URI.

    Args:
        log_entry_path (str): Task Location path or URL for a LogEntry.

    Returns:
        Optional[str]: collection path such as redfish/v1/.../Dump/Entries, or None.
    """
    path = log_entry_path.split("?", 1)[0]
    if "://" in path:
        path = path.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else path
    path = path.lstrip("/")
    if "/Entries/" not in f"/{path}":
        return None
    return path[: path.rfind("/Entries/") + len("/Entries")].lstrip("/")


def _entry_id_from_path(log_entry_path: str) -> Optional[str]:
    """Return the LogEntry Id from a Location path.

    Args:
        log_entry_path (str): Task Location path or URL.

    Returns:
        Optional[str]: entry Id, or None.
    """
    tail = log_entry_path.split("?", 1)[0].rstrip("/").rsplit("/", 1)
    if len(tail) != 2 or tail[1] in ("", "Entries"):
        return None
    return tail[1]


def _pick_member_href(body: dict[str, Any], wanted_id: Optional[str]) -> Optional[str]:
    """Pick a Members @odata.id, preferring wanted_id then the last member.

    Args:
        body (dict[str, Any]): Entries collection JSON.
        wanted_id (Optional[str]): LogEntry Id from the task Location.

    Returns:
        Optional[str]: member href, or None.
    """
    members = body.get("Members") or []
    hrefs: list[str] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        href = member.get(RF_ODATA_ID)
        if isinstance(href, str) and href.strip():
            hrefs.append(href.strip())
            extra = member.get("Id")
            if wanted_id and extra is not None and str(extra) == wanted_id:
                return href.strip()
    if wanted_id:
        suffix = "/" + wanted_id
        for href in hrefs:
            if href.rstrip("/").endswith(suffix):
                return href
        return None
    return hrefs[-1] if hrefs else None


def _get_json_if_ok(conn: RedfishConnection, path: str) -> tuple[Optional[dict[str, Any]], int]:
    """GET path and return JSON when the status is 200.

    Args:
        conn (RedfishConnection): Redfish connection.
        path (str): relative Redfish path.

    Returns:
        tuple[Optional[dict[str, Any]], int]: parsed object (or None) and status.
    """
    resp = conn.get_response(path)
    if resp.status_code != codes.ok:
        return None, resp.status_code
    try:
        body = resp.json()
    except Exception:
        return None, resp.status_code
    if isinstance(body, dict):
        return body, resp.status_code
    return None, resp.status_code


def _fetch_log_entry_json(
    conn: RedfishConnection,
    log_entry_path: str,
    log: logging.Logger,
) -> tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]:
    """GET a LogEntry, retrying 404s and falling back to the Entries collection.

    Args:
        conn (RedfishConnection): Redfish connection.
        log_entry_path (str): path from the completed task Location header.
        log (logging.Logger): logger.

    Returns:
        tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]: entry JSON,
        last HTTP status, and last exception string.
    """
    paths_to_try: list[str] = []
    log_entry_alt = _strip_port_from_url(log_entry_path)
    if log_entry_alt is None and not log_entry_path.startswith("http"):
        log_entry_alt = _strip_port_from_url(
            conn.base_url.rstrip("/") + "/" + log_entry_path.lstrip("/")
        )
    if log_entry_alt:
        paths_to_try.append(_get_path_from_connection(conn, log_entry_alt))
    rel_path = _get_path_from_connection(conn, log_entry_path)
    if rel_path not in paths_to_try:
        paths_to_try.append(rel_path)

    last_status: Optional[int] = codes.not_found
    last_error = ""
    for attempt in range(_LOG_ENTRY_GET_ATTEMPTS):
        for try_path in paths_to_try:
            if not try_path:
                continue
            try:
                body, last_status = _get_json_if_ok(conn, try_path)
                if body is not None:
                    return body, codes.ok, None
            except Exception as e:
                last_status = None
                last_error = str(e)
        if attempt < _LOG_ENTRY_GET_ATTEMPTS - 1:
            time.sleep(_LOG_ENTRY_GET_RETRY_SLEEP_S)

    coll_path = _entries_collection_path(rel_path)
    wanted_id = _entry_id_from_path(rel_path)
    if coll_path:
        log.info("LogEntry GET 404; listing %s for Id %s", coll_path, wanted_id)
        try:
            coll, coll_status = _get_json_if_ok(conn, coll_path)
        except Exception as e:
            last_error = str(e)
            coll = None
            coll_status = None
        if coll is not None:
            href = _pick_member_href(coll, wanted_id)
            if href:
                member_path = _get_path_from_connection(conn, href)
                try:
                    body, member_status = _get_json_if_ok(conn, member_path)
                    if body is not None:
                        return body, codes.ok, None
                    extra = None
                    for member in coll.get("Members") or []:
                        if isinstance(member, dict) and member.get(RF_ODATA_ID) == href:
                            extra = member
                            break
                    if extra and extra.get("AdditionalDataURI"):
                        return extra, codes.ok, None
                    last_error = f"member GET status {member_status} for {member_path}"
                except Exception as e:
                    last_error = str(e)
            else:
                last_error = f"Id {wanted_id} not in {coll_path}"
        elif coll_status is not None:
            last_error = f"Entries collection GET status {coll_status}"

    return None, last_status, last_error or None


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
                "Log metadata written to disk: %s -> %s",
                oem_diagnostic_type,
                metadata_file.name,
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
    diagnostic_data_type: str = "OEM",
) -> tuple[Optional[bytes], Optional[dict[str, Any]], Optional[str]]:
    """
    Initiate CollectDiagnosticData, poll until done, download log and metadata.

    Args:
        conn: Redfish connection (session already established).
        log_service_path: Path to LogService under Systems, e.g.
            "redfish/v1/Systems/UBB/LogServices/DiagLogs" (no leading slash).
        oem_diagnostic_type: OEM type when diagnostic_data_type is OEM (e.g. JournalControl, AllLogs).
        task_timeout_s: Max seconds to wait for BMC task
        output_dir: If set, save log archive and LogEntry JSON here.
        validate_type: If True, require oem_diagnostic_type to be in allowed_types.
        allowed_types: Allowable OEM diagnostic types for validation when validate_type is True.
        logger: Logger
        diagnostic_data_type: DMTF DiagnosticDataType (OEM, Manager, and similar).

    Returns:
        (log_bytes, log_entry_metadata_dict, error_message).
        On success: (bytes, dict, None). On failure: (None, None, error_str).
    """
    SLEEP_S_DEFAULT = 1
    log = logger if logger is not None else _module_logger
    diag_type = (diagnostic_data_type or "OEM").strip() or "OEM"
    oem_type = (oem_diagnostic_type or "").strip()
    if diag_type == "OEM" and not oem_type:
        return None, None, "oem_diagnostic_type is required"
    if validate_type and allowed_types and oem_type and oem_type not in allowed_types:
        return (
            None,
            None,
            f"oem_diagnostic_type {oem_type!r} not in allowed types",
        )
    path_prefix = log_service_path.rstrip("/")
    action_path = f"{path_prefix}/Actions/LogService.CollectDiagnosticData"
    payload: dict[str, Any] = {"DiagnosticDataType": diag_type}
    if oem_type:
        payload["OEMDiagnosticDataType"] = oem_type

    try:
        resp: RedfishHttpResponse = conn.post(action_path, json=payload)
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
    try:
        sleep_s = int(resp.headers.get("Retry-After", SLEEP_S_DEFAULT) or SLEEP_S_DEFAULT)
    except ValueError:
        sleep_s = SLEEP_S_DEFAULT
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

    task_monitor: Optional[str] = None
    task_path: Optional[str] = None
    if task_json is None:
        if isinstance(oem_response, dict) and oem_response.get(RF_ODATA_ID):
            task_path = _task_resource_path(
                _get_path_from_connection(conn, oem_response[RF_ODATA_ID])
            )
        if location_header:
            loc_path = _get_path_from_connection(conn, location_header)
            loc_task = _task_resource_path(loc_path)
            if loc_task:
                task_path = loc_task
            else:
                task_monitor = location_header
        if not task_monitor and not task_path and isinstance(oem_response, dict):
            task_monitor = _get_task_monitor_uri(oem_response, conn)
        if task_path:
            task_json, poll_err = _poll_task_resource(conn, task_path, task_timeout_s, sleep_s)
            if poll_err:
                return None, None, poll_err
        elif task_monitor:
            start = time.time()
            poll_resp = None
            while True:
                if time.time() - start > task_timeout_s:
                    return None, None, f"Task did not complete within {task_timeout_s}s"
                monitor_path = _get_path_from_connection(conn, task_monitor)
                poll_resp = conn.get_response(monitor_path)
                if poll_resp.status_code == codes.not_found:
                    return None, None, f"TaskMonitor GET failed: status {codes.not_found}"
                if poll_resp.status_code != codes.accepted:
                    break
                time.sleep(max(int(sleep_s), 1))
            try:
                monitor_body = poll_resp.json() if poll_resp else {}
            except Exception:
                monitor_body = {}
            task_uri_from_monitor = (
                monitor_body.get(RF_ODATA_ID) if isinstance(monitor_body, dict) else None
            )
            if isinstance(task_uri_from_monitor, str) and task_uri_from_monitor.strip():
                follow_path = _get_path_from_connection(conn, task_uri_from_monitor.strip())
            else:
                follow_path = _get_path_from_connection(
                    conn, task_monitor.rstrip("/").rsplit("/", 1)[0]
                )
            follow_task = _task_resource_path(follow_path)
            if follow_task:
                task_json, poll_err = _poll_task_resource(
                    conn, follow_task, task_timeout_s, sleep_s
                )
                if poll_err:
                    return None, None, poll_err
            else:
                task_resp = conn.get_response(follow_path)
                if task_resp.status_code != codes.ok:
                    return None, None, f"Task GET failed: {task_resp.status_code}"
                task_json = task_resp.json()
                if task_json.get("TaskState") != TaskState.completed.value:
                    return (
                        None,
                        None,
                        f"Task did not complete: TaskState={task_json.get('TaskState')}",
                    )
        else:
            _log_collect_diag_response(
                log, resp.status_code, oem_response, getattr(resp, "text", "") or ""
            )
            return None, None, "No TaskMonitor in response and no Location header"

    if not isinstance(task_json, dict):
        return None, None, "Task did not complete: missing task body"

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

    log_entry_json, first_status, first_error = _fetch_log_entry_json(conn, log_entry_path, log)
    if log_entry_json is None:
        if first_error:
            err = first_error
            if first_status is not None:
                err = f"{first_error} (status {first_status})"
        elif first_status is not None:
            err = f"status {first_status}"
        else:
            err = "unknown"
        return None, None, f"LogEntry GET failed: {err} (GET {log_entry_path})"

    file_stem = oem_type or diag_type
    log_bytes = _download_log_and_save(conn, log_entry_json, file_stem, output_dir, log)
    return log_bytes, log_entry_json, None
