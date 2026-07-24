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
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from framework.common.serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_HUB_VERSION_ENTRY,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_TIER_CRITICAL,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
)

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    AfidEvent,
    MI4XXCollectorArgs,
    Mi4xxServiceabilityAnalyzerArgs,
    Mi4xxServiceabilityPlugin,
    ServiceabilityDataModel,
    ServiceabilityHubAnalyzer,
    ServiceabilityPluginBase,
    analyze_serviceability_window,
    default_afid_sag_path,
    load_hub_from_entry_point,
    resolve_configured_afid_sag_path,
    run_entry_point_hub,
    serviceability_block_from_entry_point_hub,
    validate_afid_sag_path,
)
from nodescraper.plugins.serviceability.se_runner import HubRunError


class _FakeHub:
    name = "amdse"

    def analyze(self, request):
        assert request["afid_sag_path"]
        assert request["afid_events"]
        return {
            "engine": self.name,
            "engine_version": DUMMY_HUB_VERSION_ENTRY,
            "results": [
                {
                    "afid_num": request["afid_events"][0]["afid"],
                    "location": request["afid_events"][0]["serviceable_unit"],
                    "count": 1,
                    "tier": 1,
                    "tier_label": DUMMY_TIER_CRITICAL,
                    "service_action_num": DUMMY_SERVICE_ACTION_NUM,
                }
            ],
            "tier_grouped": {},
        }


def test_mi4xx_collector_args_default_helios_event_log_uri():
    args = MI4XXCollectorArgs()
    assert (
        args.resolved_event_log_uri()
        == Mi4xxServiceabilityAnalyzerArgs().resolved_rf_event_log_uri()
    )


def test_mi4xx_analyzer_args_default_helios_event_log_uri():
    args = Mi4xxServiceabilityAnalyzerArgs()
    assert args.resolved_rf_event_log_uri() == (
        "/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries"
    )


def test_mi4xx_serviceability_plugin_wiring():
    assert issubclass(Mi4xxServiceabilityPlugin, ServiceabilityPluginBase)
    assert Mi4xxServiceabilityPlugin.COLLECTOR_ARGS is MI4XXCollectorArgs
    assert Mi4xxServiceabilityPlugin.ANALYZER_ARGS is Mi4xxServiceabilityAnalyzerArgs
    assert Mi4xxServiceabilityPlugin.ANALYZER is ServiceabilityHubAnalyzer


def test_mi4xx_analyzer_args_default_hub_entry_point():
    args = Mi4xxServiceabilityAnalyzerArgs()
    assert args.hub_entry_point == "amdse"
    assert args.skip_hub is False


def test_load_hub_from_entry_point():
    fake_ep = SimpleNamespace(name="amdse", load=lambda: _FakeHub)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        hub = load_hub_from_entry_point("amdse")
    assert hub.name == "amdse"


def test_mi4xx_analyzer_args_default_afid_sag_path():
    args = Mi4xxServiceabilityAnalyzerArgs()
    assert args.resolved_afid_sag_path() == default_afid_sag_path()


def test_mi4xx_analyzer_args_override_afid_sag_path(tmp_path):
    sag = tmp_path / "custom_sag.json"
    sag.write_text("{}", encoding="utf-8")
    args = Mi4xxServiceabilityAnalyzerArgs(afid_sag_path=str(sag))
    assert args.resolved_afid_sag_path() == str(sag)


def test_resolve_configured_afid_sag_path_prefers_explicit(tmp_path):
    sag = tmp_path / "override.json"
    sag.write_text("{}", encoding="utf-8")
    assert resolve_configured_afid_sag_path(str(sag)) == str(sag)


def test_validate_afid_sag_path_validates_file(tmp_path):
    sag = tmp_path / "afid_sag.json"
    sag.write_text("{}", encoding="utf-8")
    assert validate_afid_sag_path(str(sag)) == str(sag)


def test_run_entry_point_hub(tmp_path):
    sag = tmp_path / "afid_sag.json"
    sag.write_text("{}", encoding="utf-8")
    fake_ep = SimpleNamespace(name="amdse", load=lambda: _FakeHub)
    events = [AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP)]
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        block = run_entry_point_hub(
            hub_entry_point="amdse",
            afid_events=events,
            afid_sag_path=str(sag),
        )
    assert block.hub_version == DUMMY_HUB_VERSION_ENTRY
    assert len(block.solution) == 1


def test_serviceability_block_from_entry_point_hub():
    events = [AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP)]
    block = serviceability_block_from_entry_point_hub(
        events,
        {
            "engine": "amdse",
            "engine_version": DUMMY_HUB_VERSION_ENTRY,
            "results": [
                {
                    "afid_num": DUMMY_AFID_A,
                    "location": DUMMY_UNIT_A,
                    "service_action_num": DUMMY_SERVICE_ACTION_NUM,
                    "tier_label": DUMMY_TIER_CRITICAL,
                }
            ],
        },
        rf_event_count=3,
    )
    assert len(block.solution) == 1
    assert block.solution[0].afid == DUMMY_AFID_A
    assert block.solution[0].service_action_num == DUMMY_SERVICE_ACTION_NUM
    assert block.hub_version == DUMMY_HUB_VERSION_ENTRY


def test_analyze_serviceability_window_skip_hub():
    data = ServiceabilityDataModel(
        rf_events=[
            {"Afid": DUMMY_AFID_A, "ServiceableUnit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP}
        ]
    )
    args = Mi4xxServiceabilityAnalyzerArgs(skip_hub=True)
    result = analyze_serviceability_window(data, args)
    assert result.ok
    assert result.serviceability is not None
    assert len(result.afid_events) == 1


def test_serviceability_hub_analyzer_runs_entry_point_hub(system_info, tmp_path):
    sag = tmp_path / "afid_sag.json"
    sag.write_text("{}", encoding="utf-8")
    data = ServiceabilityDataModel(
        rf_events=[
            {"Afid": DUMMY_AFID_A, "ServiceableUnit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP}
        ]
    )
    fake_ep = SimpleNamespace(name="amdse", load=lambda: _FakeHub)
    analyzer = ServiceabilityHubAnalyzer(system_info=system_info)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        task = analyzer.analyze_data(
            data,
            Mi4xxServiceabilityAnalyzerArgs(afid_sag_path=str(sag)),
        )
    assert task.status == ExecutionStatus.OK
    assert "amdse" in task.message


def test_load_hub_from_entry_point_missing_raises():
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[],
    ):
        with pytest.raises(HubRunError, match="not found"):
            load_hub_from_entry_point("missing")
