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
from unittest.mock import MagicMock

from requests.status_codes import codes

from nodescraper.connection.redfish import RedfishConnectionError
from nodescraper.connection.redfish.redfish_oem_diag import (
    DEFAULT_TASK_TIMEOUT_S,
    RF_ANNOTATION_ALLOWABLE,
    _download_log_and_save,
    _get_task_monitor_uri,
    _strip_port_from_url,
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
