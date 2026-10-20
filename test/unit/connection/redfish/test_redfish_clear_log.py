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
from unittest.mock import MagicMock

from nodescraper.connection.redfish.redfish_clear_log import (
    ClearLogEndpoint,
    _odata_id_to_path,
    _parse_clear_endpoint,
    clear_redfish_logs,
    discover_clear_log_endpoints,
)
from nodescraper.connection.redfish.redfish_connection import RedfishConnectionError


def _ok_resp(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = body
    return resp


def _err_resp(status: int = 404) -> MagicMock:
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.json.return_value = {}
    return resp


class TestOdataIdToPath:
    def test_relative_path(self):
        assert _odata_id_to_path("/redfish/v1/Systems", "") == "redfish/v1/Systems"

    def test_strips_leading_slash(self):
        assert _odata_id_to_path("/redfish/v1", "") == "redfish/v1"

    def test_full_url_extracts_path(self):
        result = _odata_id_to_path("https://bmc/redfish/v1/Systems/1", "")
        assert result == "redfish/v1/Systems/1"

    def test_strips_base_url(self):
        result = _odata_id_to_path(
            "https://bmc/redfish/v1/Systems",
            "https://bmc",
        )
        assert result == "redfish/v1/Systems"

    def test_empty_returns_empty(self):
        assert _odata_id_to_path("", "") == ""

    def test_none_returns_empty(self):
        assert _odata_id_to_path(None, "") == ""  # type: ignore[arg-type]


class TestParseClearEndpoint:
    def test_hash_prefixed_action(self):
        svc_data = {
            "Actions": {
                "#LogService.ClearLog": {
                    "target": "/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/LogService.ClearLog"
                }
            },
            "OverWritePolicy": "WrapsWhenFull",
        }
        result = _parse_clear_endpoint(svc_data)
        assert result is not None
        assert (
            result.path
            == "/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/LogService.ClearLog"
        )
        assert result.overwrite_policy == "WrapsWhenFull"

    def test_unprefixed_action(self):
        svc_data = {
            "Actions": {
                "LogService.ClearLog": {
                    "target": "/redfish/v1/Managers/BMC/LogServices/Log/Actions/LogService.ClearLog"
                }
            }
        }
        result = _parse_clear_endpoint(svc_data)
        assert result is not None
        assert "ClearLog" in result.path

    def test_no_clear_action_returns_none(self):
        svc_data = {"Actions": {"#LogService.CollectDiagnosticData": {"target": "/some/path"}}}
        assert _parse_clear_endpoint(svc_data) is None

    def test_empty_target_returns_none(self):
        svc_data = {"Actions": {"#LogService.ClearLog": {"target": ""}}}
        assert _parse_clear_endpoint(svc_data) is None

    def test_missing_actions_returns_none(self):
        assert _parse_clear_endpoint({}) is None

    def test_default_overwrite_policy_empty_string(self):
        svc_data = {"Actions": {"#LogService.ClearLog": {"target": "/path"}}}
        result = _parse_clear_endpoint(svc_data)
        assert result is not None
        assert result.overwrite_policy == ""

    def test_never_overwrite_policy_preserved(self):
        svc_data = {
            "Actions": {"#LogService.ClearLog": {"target": "/path"}},
            "OverWritePolicy": "NeverOverWrites",
        }
        result = _parse_clear_endpoint(svc_data)
        assert result is not None
        assert result.overwrite_policy == "NeverOverWrites"


class TestClearRedfishLogs:
    def test_success(self):
        conn = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        conn.post.return_value = resp

        endpoints = [ClearLogEndpoint(path="/path/ClearLog")]
        results = clear_redfish_logs(conn, endpoints)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].status_code == 200
        conn.post.assert_called_once_with("/path/ClearLog", json={})

    def test_failure_non_ok_response(self):
        conn = MagicMock()
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 500
        conn.post.return_value = resp

        endpoints = [ClearLogEndpoint(path="/path/ClearLog")]
        results = clear_redfish_logs(conn, endpoints)
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].status_code == 500
        assert "500" in results[0].error

    def test_connection_error_returns_failure(self):
        conn = MagicMock()
        conn.post.side_effect = RedfishConnectionError("connection refused")

        endpoints = [ClearLogEndpoint(path="/path/ClearLog")]
        results = clear_redfish_logs(conn, endpoints)
        assert len(results) == 1
        assert results[0].success is False
        assert "connection refused" in results[0].error

    def test_never_overwrite_skipped(self):
        conn = MagicMock()
        endpoints = [ClearLogEndpoint(path="/path", overwrite_policy="NeverOverWrites")]
        results = clear_redfish_logs(conn, endpoints)
        assert results == []
        conn.post.assert_not_called()

    def test_mixed_never_overwrite_and_clearable(self):
        conn = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 204
        conn.post.return_value = resp

        endpoints = [
            ClearLogEndpoint(path="/clear/a"),
            ClearLogEndpoint(path="/clear/b", overwrite_policy="NeverOverWrites"),
        ]
        results = clear_redfish_logs(conn, endpoints)
        assert len(results) == 1
        assert results[0].path == "/clear/a"
        conn.post.assert_called_once_with("/clear/a", json={})

    def test_continues_on_first_failure(self):
        conn = MagicMock()

        def post_side(path, json):
            r = MagicMock()
            r.ok = path != "/bad"
            r.status_code = 500 if path == "/bad" else 200
            return r

        conn.post.side_effect = post_side
        endpoints = [ClearLogEndpoint(path="/bad"), ClearLogEndpoint(path="/good")]
        results = clear_redfish_logs(conn, endpoints)
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True

    def test_empty_endpoints_returns_empty(self):
        conn = MagicMock()
        assert clear_redfish_logs(conn, []) == []
        conn.post.assert_not_called()


class TestDiscoverClearLogEndpoints:
    def _make_conn(self, api_root="redfish/v1", base_url="https://bmc"):
        conn = MagicMock()
        conn.api_root = api_root
        conn.base_url = base_url
        return conn

    def test_discovers_clear_endpoint(self):
        conn = self._make_conn()

        systems_body = {"Members": [{"@odata.id": "/redfish/v1/Systems/UBB"}]}
        ls_list_body = {"Members": [{"@odata.id": "/redfish/v1/Systems/UBB/LogServices/DiagLogs"}]}
        svc_body = {
            "Actions": {
                "#LogService.ClearLog": {
                    "target": "/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/LogService.ClearLog"
                }
            },
            "OverWritePolicy": "WrapsWhenFull",
        }

        def get_response(path):
            if "Systems" == path.strip("/").split("/")[-1] or path.endswith("/Systems"):
                return _ok_resp(systems_body)
            if "LogServices" in path and path.endswith("LogServices"):
                return _ok_resp(ls_list_body)
            if "DiagLogs" in path and "Actions" not in path:
                return _ok_resp(svc_body)
            return _err_resp()

        conn.get_response.side_effect = get_response
        results = discover_clear_log_endpoints(conn, roots=["Systems"])
        assert len(results) == 1
        assert "ClearLog" in results[0].path
        assert results[0].overwrite_policy == "WrapsWhenFull"

    def test_skips_member_with_no_log_services(self):
        conn = self._make_conn()

        def get_response(path):
            if path.endswith("/Systems"):
                return _ok_resp({"Members": [{"@odata.id": "/redfish/v1/Systems/UBB"}]})
            if "LogServices" in path:
                return _err_resp(404)
            return _err_resp()

        conn.get_response.side_effect = get_response
        results = discover_clear_log_endpoints(conn, roots=["Systems"])
        assert results == []

    def test_skips_service_without_clear_action(self):
        conn = self._make_conn()

        def get_response(path):
            if path.endswith("/Systems"):
                return _ok_resp({"Members": [{"@odata.id": "/redfish/v1/Systems/UBB"}]})
            if path.endswith("/LogServices"):
                return _ok_resp(
                    {"Members": [{"@odata.id": "/redfish/v1/Systems/UBB/LogServices/EventLog"}]}
                )
            if path.endswith("/EventLog"):
                return _ok_resp(
                    {"Actions": {"#LogService.CollectDiagnosticData": {"target": "/collect"}}}
                )
            return _err_resp()

        conn.get_response.side_effect = get_response
        results = discover_clear_log_endpoints(conn, roots=["Systems"])
        assert results == []

    def test_explicit_member_ids_skip_root_get(self):
        conn = self._make_conn()

        svc_body = {
            "Actions": {
                "#LogService.ClearLog": {
                    "target": "/redfish/v1/Managers/AMC/LogServices/Log/Actions/LogService.ClearLog"
                }
            }
        }

        def get_response(path):
            if path.endswith("/LogServices"):
                return _ok_resp(
                    {"Members": [{"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Log"}]}
                )
            if path.endswith("/Log"):
                return _ok_resp(svc_body)
            return _err_resp()

        conn.get_response.side_effect = get_response
        results = discover_clear_log_endpoints(
            conn, roots=["Managers"], member_ids={"Managers": ["AMC"]}
        )
        assert len(results) == 1
        # Root collection GET should never have been called
        calls = [str(c) for c in conn.get_response.call_args_list]
        assert not any(
            "Managers'" == p.strip("'").strip("/").split("/")[-1]
            for p in calls
            if "LogServices" not in p and "Log" not in p
        )

    def test_connection_error_on_root_is_skipped(self):
        conn = self._make_conn()
        conn.get_response.side_effect = RedfishConnectionError("timeout")
        results = discover_clear_log_endpoints(conn, roots=["Systems"])
        assert results == []

    def test_non_ok_root_response_is_skipped(self):
        conn = self._make_conn()
        conn.get_response.return_value = _err_resp(503)
        results = discover_clear_log_endpoints(conn, roots=["Systems"])
        assert results == []

    def test_multiple_roots_combined(self):
        conn = self._make_conn()

        clear_target_systems = (
            "/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/LogService.ClearLog"
        )
        clear_target_managers = (
            "/redfish/v1/Managers/AMC/LogServices/Log/Actions/LogService.ClearLog"
        )

        def get_response(path):
            if path.endswith("/redfish/v1/Systems"):
                return _ok_resp({"Members": [{"@odata.id": "/redfish/v1/Systems/UBB"}]})
            if path.endswith("/redfish/v1/Managers"):
                return _ok_resp({"Members": [{"@odata.id": "/redfish/v1/Managers/AMC"}]})
            if path.rstrip("/") == "/redfish/v1/Systems/UBB/LogServices":
                return _ok_resp(
                    {"Members": [{"@odata.id": "/redfish/v1/Systems/UBB/LogServices/DiagLogs"}]}
                )
            if path.rstrip("/") == "/redfish/v1/Managers/AMC/LogServices":
                return _ok_resp(
                    {"Members": [{"@odata.id": "/redfish/v1/Managers/AMC/LogServices/Log"}]}
                )
            if path.rstrip("/") == "/redfish/v1/Systems/UBB/LogServices/DiagLogs":
                return _ok_resp(
                    {"Actions": {"#LogService.ClearLog": {"target": clear_target_systems}}}
                )
            if path.rstrip("/") == "/redfish/v1/Managers/AMC/LogServices/Log":
                return _ok_resp(
                    {"Actions": {"#LogService.ClearLog": {"target": clear_target_managers}}}
                )
            return _err_resp()

        conn.get_response.side_effect = get_response
        results = discover_clear_log_endpoints(conn, roots=["Systems", "Managers"])
        assert len(results) == 2
        paths = {r.path for r in results}
        assert clear_target_systems in paths
        assert clear_target_managers in paths
