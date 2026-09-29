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
import logging
from unittest.mock import MagicMock, patch

from requests.status_codes import codes

from nodescraper.connection.redfish import RedfishConnectionError
from nodescraper.connection.redfish.redfish_oem_diag import (
    DEFAULT_TASK_TIMEOUT_S,
    RF_ANNOTATION_ALLOWABLE,
    _download_log_and_save,
    _entries_collection_path,
    _get_task_monitor_uri,
    _pick_member_href,
    _strip_port_from_url,
    _task_resource_path,
    collect_oem_diagnostic_data,
    get_oem_diagnostic_allowable_values,
)


def test_rf_annotation_allowable_constant():
    assert RF_ANNOTATION_ALLOWABLE == "OEMDiagnosticDataType@Redfish.AllowableValues"


def test_default_task_timeout_s():
    assert DEFAULT_TASK_TIMEOUT_S == 1800


class TestGetOemDiagnosticAllowableValues:
    def test_returns_list_from_collect_action(self):
        conn = MagicMock()
        conn.get.return_value = {
            "Actions": {
                "LogService.CollectDiagnosticData": {
                    "OEMDiagnosticDataType@Redfish.AllowableValues": ["Dmesg", "AllLogs"],
                }
            }
        }
        result = get_oem_diagnostic_allowable_values(
            conn, "redfish/v1/Systems/1/LogServices/DiagLogs"
        )
        assert result == ["Dmesg", "AllLogs"]

    def test_returns_list_from_octothorpe_action_key(self):
        conn = MagicMock()
        conn.get.return_value = {
            "Actions": {
                "#LogService.CollectDiagnosticData": {
                    "OEMDiagnosticDataType@Redfish.AllowableValues": ["JournalControl"],
                }
            }
        }
        result = get_oem_diagnostic_allowable_values(
            conn, "redfish/v1/Systems/UBB/LogServices/DiagLogs"
        )
        assert result == ["JournalControl"]

    def test_returns_none_on_connection_error(self):
        conn = MagicMock()
        conn.get.side_effect = RedfishConnectionError("fail")
        result = get_oem_diagnostic_allowable_values(conn, "redfish/v1/LogServices/DiagLogs")
        assert result is None

    def test_returns_none_when_data_not_dict(self):
        conn = MagicMock()
        conn.get.return_value = []
        result = get_oem_diagnostic_allowable_values(conn, "redfish/v1/LogServices/DiagLogs")
        assert result is None

    def test_returns_none_when_no_actions(self):
        conn = MagicMock()
        conn.get.return_value = {}
        result = get_oem_diagnostic_allowable_values(conn, "redfish/v1/LogServices/DiagLogs")
        assert result is None


class TestStripPortFromUrl:
    def test_strips_port_443(self):
        url = "https://host:443/redfish/v1/TaskService/Tasks/1"
        assert _strip_port_from_url(url) == "https://host/redfish/v1/TaskService/Tasks/1"

    def test_strips_other_port(self):
        url = "https://host:8443/redfish/v1"
        assert _strip_port_from_url(url) == "https://host/redfish/v1"

    def test_returns_none_when_no_port(self):
        url = "https://host/redfish/v1"
        assert _strip_port_from_url(url) is None

    def test_returns_none_for_relative_path(self):
        assert _strip_port_from_url("redfish/v1/Systems/1") is None


class TestGetTaskMonitorUri:
    def test_returns_task_monitor_from_body(self):
        conn = MagicMock()
        conn.base_url = "https://host/redfish/v1"
        body = {"TaskMonitor": "TaskService/Tasks/1/Monitor"}
        result = _get_task_monitor_uri(body, conn)
        assert result == "https://host/redfish/v1/TaskService/Tasks/1/Monitor"

    def test_returns_from_odata_id_plus_monitor(self):
        conn = MagicMock()
        conn.base_url = "https://host/redfish/v1"
        body = {"@odata.id": "TaskService/Tasks/1"}
        result = _get_task_monitor_uri(body, conn)
        assert result == "https://host/redfish/v1/TaskService/Tasks/1/Monitor"

    def test_returns_none_for_empty_body(self):
        conn = MagicMock()
        assert _get_task_monitor_uri({}, conn) is None

    def test_prefers_task_monitor_over_odata_id(self):
        conn = MagicMock()
        conn.base_url = "https://host/redfish/v1"
        body = {
            "TaskMonitor": "TaskService/Tasks/1/Monitor",
            "@odata.id": "TaskService/Tasks/2",
        }
        result = _get_task_monitor_uri(body, conn)
        assert result == "https://host/redfish/v1/TaskService/Tasks/1/Monitor"


class TestDownloadLogAndSave:
    def test_returns_none_when_no_additional_data_uri(self):
        conn = MagicMock()
        log_entry_json = {"Id": "1", "Name": "LogEntry"}
        result = _download_log_and_save(
            conn, log_entry_json, "Dmesg", None, logging.getLogger("test")
        )
        assert result is None
        conn.get_response.assert_not_called()

    def test_downloads_and_returns_bytes_when_additional_data_uri_present(self):
        conn = MagicMock()
        conn.base_url = "https://host/redfish/v1"
        resp = MagicMock()
        resp.status_code = codes.ok
        resp.content = b"log bytes"
        conn.get_response.return_value = resp
        log_entry_json = {"AdditionalDataURI": "/redfish/v1/LogServices/1/Entries/1/Attachment"}
        result = _download_log_and_save(
            conn, log_entry_json, "Dmesg", None, logging.getLogger("test")
        )
        assert result == b"log bytes"
        conn.get_response.assert_called_once()

    def test_writes_archive_and_metadata_to_output_dir(self, tmp_path):
        conn = MagicMock()
        conn.base_url = "https://host/redfish/v1"
        resp = MagicMock()
        resp.status_code = codes.ok
        resp.content = b"log bytes"
        conn.get_response.return_value = resp
        log_entry_json = {
            "AdditionalDataURI": "/redfish/v1/LogServices/1/Entries/1/Attachment",
            "Id": "1",
        }
        result = _download_log_and_save(
            conn, log_entry_json, "AllLogs", tmp_path, logging.getLogger("test")
        )
        assert result == b"log bytes"
        assert (tmp_path / "AllLogs.tar.xz").read_bytes() == b"log bytes"
        metadata = (tmp_path / "AllLogs_log_entry.json").read_text(encoding="utf-8")
        assert "Id" in metadata and "1" in metadata


def test_collect_manager_diagnostic_payload():
    conn = MagicMock()
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "fail"
    conn.post.return_value = resp
    collect_oem_diagnostic_data(
        conn,
        "redfish/v1/Managers/dummy-amc/LogServices/Dump",
        diagnostic_data_type="Manager",
    )
    payload = conn.post.call_args.kwargs["json"]
    assert payload == {"DiagnosticDataType": "Manager"}


def test_task_resource_path_accepts_tasks_not_monitors():
    assert (
        _task_resource_path("/redfish/v1/TaskService/Tasks/dummy-1")
        == "redfish/v1/TaskService/Tasks/dummy-1"
    )
    assert _task_resource_path("redfish/v1/TaskService/TaskMonitors/1") is None


def test_collect_polls_task_resource_until_completed():
    conn = MagicMock()
    conn.base_url = "https://bmc.example.test"
    post_resp = MagicMock()
    post_resp.status_code = codes.accepted
    post_resp.headers = {"Location": "/redfish/v1/TaskService/TaskMonitors/1"}
    post_resp.text = ""
    post_resp.json.return_value = {
        "@odata.id": "/redfish/v1/TaskService/Tasks/dummy-1",
        "TaskState": "Running",
    }
    conn.post.return_value = post_resp

    running = MagicMock()
    running.status_code = codes.ok
    running.json.return_value = {"TaskState": "Running"}
    done = MagicMock()
    done.status_code = codes.ok
    done.json.return_value = {
        "TaskState": "Completed",
        "Payload": {
            "HttpHeaders": [
                "Location: /redfish/v1/Systems/dummy-system/LogServices/DiagLogs/Entries/1"
            ]
        },
    }
    entry = MagicMock()
    entry.status_code = codes.ok
    entry.json.return_value = {
        "Id": "1",
        "AdditionalDataURI": (
            "/redfish/v1/Systems/dummy-system/LogServices/DiagLogs/Entries/1/attachment"
        ),
    }
    attachment = MagicMock()
    attachment.status_code = codes.ok
    attachment.content = b"archive"
    conn.get_response.side_effect = [running, done, entry, attachment]

    with patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep"):
        log_bytes, metadata, err = collect_oem_diagnostic_data(
            conn,
            "redfish/v1/Systems/dummy-system/LogServices/DiagLogs",
            oem_diagnostic_type="AllLogs",
            task_timeout_s=30,
        )
    assert err is None
    assert log_bytes == b"archive"
    assert metadata is not None
    assert metadata["Id"] == "1"
    polled = [c.args[0] for c in conn.get_response.call_args_list]
    assert polled[0] == "redfish/v1/TaskService/Tasks/dummy-1"
    assert polled[1] == "redfish/v1/TaskService/Tasks/dummy-1"


def test_collect_taskmonitor_404_does_not_spin():
    conn = MagicMock()
    conn.base_url = "https://bmc.example.test"
    post_resp = MagicMock()
    post_resp.status_code = codes.accepted
    post_resp.headers = {"Location": "/redfish/v1/TaskService/TaskMonitors/1"}
    post_resp.text = ""
    post_resp.json.return_value = {}
    conn.post.return_value = post_resp
    missing = MagicMock()
    missing.status_code = codes.not_found
    conn.get_response.return_value = missing

    _log_bytes, _metadata, err = collect_oem_diagnostic_data(
        conn,
        "redfish/v1/Systems/dummy-system/LogServices/DiagLogs",
        oem_diagnostic_type="AllLogs",
        task_timeout_s=30,
    )
    assert err is not None
    assert "404" in err
    assert conn.get_response.call_count == 1


class TestCollectOemDiagnosticDataRetryAfter:
    @staticmethod
    def _conn_for_retry_after(retry_after: str) -> MagicMock:
        conn = MagicMock()
        conn.base_url = "https://host"
        post_resp = MagicMock()
        post_resp.status_code = codes.accepted
        post_resp.headers = {
            "Location": "/redfish/v1/TaskService/TaskMonitors/1",
            "Retry-After": retry_after,
        }
        post_resp.json.return_value = {}
        conn.post.return_value = post_resp

        accepted = MagicMock()
        accepted.status_code = codes.accepted
        accepted.json.return_value = {}
        monitor_resp = MagicMock()
        monitor_resp.status_code = codes.ok
        monitor_resp.json.return_value = {"@odata.id": "/redfish/v1/TaskService/Tasks/1"}
        task_resp = MagicMock()
        task_resp.status_code = codes.ok
        task_resp.json.return_value = {"TaskState": "Completed", "Payload": {"HttpHeaders": []}}
        conn.get_response.side_effect = [accepted, monitor_resp, task_resp]
        return conn

    @patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep")
    def test_numeric_retry_after_is_used_as_poll_interval(self, mock_sleep):
        """A Retry-After in seconds drives the poll interval after a 202 monitor."""
        conn = self._conn_for_retry_after("3")

        _, _, error = collect_oem_diagnostic_data(
            conn, "redfish/v1/Systems/UBB/LogServices/DiagLogs", "AllLogs"
        )

        assert error == "Location header missing in task Payload.HttpHeaders"
        mock_sleep.assert_called_with(3)

    @patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep")
    def test_http_date_retry_after_does_not_raise(self, mock_sleep):
        """An HTTP-date Retry-After must be handled, not crash the collection."""
        conn = self._conn_for_retry_after("Fri, 31 Dec 1999 23:59:59 GMT")

        _, _, error = collect_oem_diagnostic_data(
            conn, "redfish/v1/Systems/UBB/LogServices/DiagLogs", "AllLogs"
        )

        assert error == "Location header missing in task Payload.HttpHeaders"
        mock_sleep.assert_called_with(1)


def test_entries_collection_path_from_dump_entry():
    assert (
        _entries_collection_path("redfish/v1/Managers/AMC/LogServices/Dump/Entries/29")
        == "redfish/v1/Managers/AMC/LogServices/Dump/Entries"
    )


def test_pick_member_href_prefers_wanted_id():
    body = {
        "Members": [
            {"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/28"},
            {"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/29"},
        ]
    }
    assert _pick_member_href(body, "29") == "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/29"
    assert _pick_member_href(body, "31") is None
    assert _pick_member_href({"Members": []}, "29") is None


def _dump_collect_conn(get_side_effect):
    conn = MagicMock()
    conn.base_url = "http://192.0.2.1"
    post_resp = MagicMock()
    post_resp.status_code = codes.accepted
    post_resp.headers = {"Location": "/redfish/v1/TaskService/TaskMonitors/1"}
    post_resp.text = ""
    post_resp.json.return_value = {
        "@odata.id": "/redfish/v1/TaskService/Tasks/dummy-1",
        "TaskState": "Running",
    }
    conn.post.return_value = post_resp
    conn.get_response.side_effect = get_side_effect
    return conn


def _ok_json(payload):
    resp = MagicMock()
    resp.status_code = codes.ok
    resp.json.return_value = payload
    return resp


def _status(code):
    resp = MagicMock()
    resp.status_code = code
    resp.json.return_value = {}
    return resp


@patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep")
def test_collect_retries_log_entry_404(mock_sleep):
    """Dump LogEntry 404s are retried before failing."""
    running = _ok_json({"TaskState": "Running"})
    done = _ok_json(
        {
            "TaskState": "Completed",
            "Payload": {
                "HttpHeaders": ["Location: /redfish/v1/Managers/AMC/LogServices/Dump/Entries/29"]
            },
        }
    )
    entry = _ok_json(
        {
            "Id": "29",
            "AdditionalDataURI": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/29/attachment",
        }
    )
    attachment = MagicMock()
    attachment.status_code = codes.ok
    attachment.content = b"mgr-dump"
    conn = _dump_collect_conn([running, done, _status(codes.not_found), entry, attachment])

    log_bytes, metadata, err = collect_oem_diagnostic_data(
        conn,
        "redfish/v1/Managers/AMC/LogServices/Dump",
        diagnostic_data_type="Manager",
        task_timeout_s=30,
    )

    assert err is None
    assert log_bytes == b"mgr-dump"
    assert metadata["Id"] == "29"
    mock_sleep.assert_called()


@patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep")
def test_collect_log_entry_falls_back_to_entries_collection(mock_sleep):
    """After LogEntry 404s, list Dump/Entries and GET the matching member."""
    running = _ok_json({"TaskState": "Running"})
    done = _ok_json(
        {
            "TaskState": "Completed",
            "Payload": {
                "HttpHeaders": ["Location: /redfish/v1/Managers/AMC/LogServices/Dump/Entries/29"]
            },
        }
    )
    missing = _status(codes.not_found)
    coll = _ok_json(
        {
            "Members": [
                {"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/28"},
                {"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/29"},
            ]
        }
    )
    member = _ok_json(
        {
            "Id": "29",
            "AdditionalDataURI": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/29/attachment",
        }
    )
    attachment = MagicMock()
    attachment.status_code = codes.ok
    attachment.content = b"mgr-dump"
    conn = _dump_collect_conn(
        [running, done, missing, missing, missing, missing, coll, member, attachment]
    )

    log_bytes, metadata, err = collect_oem_diagnostic_data(
        conn,
        "redfish/v1/Managers/AMC/LogServices/Dump",
        diagnostic_data_type="Manager",
        task_timeout_s=30,
    )

    assert err is None
    assert log_bytes == b"mgr-dump"
    assert metadata["Id"] == "29"
    listed = [c.args[0] for c in conn.get_response.call_args_list]
    assert "redfish/v1/Managers/AMC/LogServices/Dump/Entries" in listed


@patch("nodescraper.connection.redfish.redfish_oem_diag.time.sleep")
def test_collect_log_entry_collection_miss_keeps_entry_status(mock_sleep):
    """Collection 200 without the requested Id must not report status 200."""
    running = _ok_json({"TaskState": "Running"})
    done = _ok_json(
        {
            "TaskState": "Completed",
            "Payload": {
                "HttpHeaders": ["Location: /redfish/v1/Managers/AMC/LogServices/Dump/Entries/31"]
            },
        }
    )
    missing = _status(codes.not_found)
    coll = _ok_json(
        {
            "Members": [
                {"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Dump/Entries/30"},
            ]
        }
    )
    conn = _dump_collect_conn([running, done, missing, missing, missing, missing, coll])

    log_bytes, metadata, err = collect_oem_diagnostic_data(
        conn,
        "redfish/v1/Managers/AMC/LogServices/Dump",
        diagnostic_data_type="Manager",
        task_timeout_s=30,
    )

    assert log_bytes is None
    assert metadata is None
    assert err is not None
    assert "status 200" not in err
    assert "status 404" in err
    assert "Id 31 not in redfish/v1/Managers/AMC/LogServices/Dump/Entries" in err
