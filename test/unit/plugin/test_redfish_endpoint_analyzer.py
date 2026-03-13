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
import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.ooband.redfish_endpoint import (
    RedfishEndpointAnalyzer,
    RedfishEndpointAnalyzerArgs,
    RedfishEndpointDataModel,
)
from nodescraper.plugins.ooband.redfish_endpoint.endpoint_analyzer import (
    _check_constraint,
    _get_by_path,
)


@pytest.fixture
def redfish_endpoint_analyzer(system_info):
    return RedfishEndpointAnalyzer(system_info=system_info)


def test_get_by_path_empty_returns_obj():
    obj = {"a": 1}
    assert _get_by_path(obj, "") == obj
    assert _get_by_path(obj, "   ") == obj


def test_get_by_path_single_key():
    assert _get_by_path({"x": 42}, "x") == 42
    assert _get_by_path({"Status": {"Health": "OK"}}, "Status") == {"Health": "OK"}


def test_get_by_path_nested_slash():
    obj = {"Status": {"Health": "OK", "State": "Enabled"}}
    assert _get_by_path(obj, "Status/Health") == "OK"
    assert _get_by_path(obj, "Status/State") == "Enabled"


def test_get_by_path_list_index():
    obj = {"PowerControl": [{"PowerConsumedWatts": 100}, {"PowerConsumedWatts": 200}]}
    assert _get_by_path(obj, "PowerControl/0/PowerConsumedWatts") == 100
    assert _get_by_path(obj, "PowerControl/1/PowerConsumedWatts") == 200


def test_get_by_path_missing_returns_none():
    assert _get_by_path({"a": 1}, "b") is None
    assert _get_by_path({"a": {"b": 2}}, "a/c") is None
    assert _get_by_path(None, "a") is None


def test_get_by_path_invalid_list_index():
    obj = {"list": [1, 2, 3]}
    assert _get_by_path(obj, "list/10") is None
    assert _get_by_path(obj, "list/xyz") is None


def test_check_constraint_eq_pass():
    ok, msg = _check_constraint("On", {"eq": "On"})
    assert ok is True


def test_check_constraint_eq_fail():
    ok, msg = _check_constraint("Off", {"eq": "On"})
    assert ok is False
    assert "On" in msg and "Off" in msg


def test_check_constraint_min_max_pass():
    ok, _ = _check_constraint(50, {"min": 0, "max": 100})
    assert ok is True
    ok, _ = _check_constraint(0, {"min": 0})
    assert ok is True
    ok, _ = _check_constraint(100, {"max": 100})
    assert ok is True


def test_check_constraint_min_fail():
    ok, msg = _check_constraint(10, {"min": 20})
    assert ok is False
    assert "below min" in msg or "20" in msg


def test_check_constraint_max_fail():
    ok, msg = _check_constraint(150, {"max": 100})
    assert ok is False
    assert "above max" in msg or "100" in msg


def test_check_constraint_any_of_pass():
    ok, _ = _check_constraint("OK", {"anyOf": ["OK", "Warning"]})
    assert ok is True
    ok, _ = _check_constraint("Warning", {"anyOf": ["OK", "Warning"]})
    assert ok is True


def test_check_constraint_any_of_fail():
    ok, msg = _check_constraint("Critical", {"anyOf": ["OK", "Warning"]})
    assert ok is False
    assert "any of" in msg or "OK" in msg


def test_check_constraint_literal_match():
    ok, _ = _check_constraint("On", "On")
    assert ok is True
    ok, msg = _check_constraint("Off", "On")
    assert ok is False


def test_redfish_endpoint_analyzer_no_checks(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(responses={"/redfish/v1": {}})
    result = redfish_endpoint_analyzer.analyze_data(data, args=None)
    assert result.status == ExecutionStatus.OK
    assert result.message == "No checks configured"


def test_redfish_endpoint_analyzer_empty_checks(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(responses={"/redfish/v1": {"Status": {"Health": "OK"}}})
    result = redfish_endpoint_analyzer.analyze_data(
        data, args=RedfishEndpointAnalyzerArgs(checks={})
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == "No checks configured"


def test_redfish_endpoint_analyzer_all_pass(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(
        responses={
            "/redfish/v1/Systems/1": {"Status": {"Health": "OK"}, "PowerState": "On"},
        }
    )
    args = RedfishEndpointAnalyzerArgs(
        checks={
            "/redfish/v1/Systems/1": {
                "Status/Health": {"anyOf": ["OK", "Warning"]},
                "PowerState": "On",
            },
        }
    )
    result = redfish_endpoint_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "All Redfish endpoint checks passed"


def test_redfish_endpoint_analyzer_one_fail(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(
        responses={
            "/redfish/v1/Systems/1": {"Status": {"Health": "Critical"}},
        }
    )
    args = RedfishEndpointAnalyzerArgs(
        checks={
            "/redfish/v1/Systems/1": {"Status/Health": {"anyOf": ["OK", "Warning"]}},
        }
    )
    result = redfish_endpoint_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.ERROR
    assert "check(s) failed" in result.message


def test_redfish_endpoint_analyzer_uri_not_in_responses(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(responses={"/redfish/v1": {}})
    args = RedfishEndpointAnalyzerArgs(
        checks={
            "/redfish/v1/Systems/1": {"Status/Health": "OK"},
        }
    )
    result = redfish_endpoint_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.ERROR
    assert "check(s) failed" in result.message or "failed" in result.message


def test_redfish_endpoint_analyzer_wildcard_applies_to_all_bodies(redfish_endpoint_analyzer):
    data = RedfishEndpointDataModel(
        responses={
            "/redfish/v1/Chassis/1": {"Status": {"Health": "OK"}},
            "/redfish/v1/Chassis/2": {"Status": {"Health": "OK"}},
        }
    )
    args = RedfishEndpointAnalyzerArgs(
        checks={
            "*": {"Status/Health": {"anyOf": ["OK", "Warning"]}},
        }
    )
    result = redfish_endpoint_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "All Redfish endpoint checks passed"
