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
from serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_BMC_HOST,
    DUMMY_EVENT_URI,
    DUMMY_HUB_VERSION_ENTRY,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_TIER_CRITICAL,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
)

from nodescraper.connection.redfish import (
    RF_MEMBERS,
    RF_MEMBERS_COUNT,
    RF_MEMBERS_NEXT_LINK,
    RedfishGetResult,
)
from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    AfidEvent,
    MI4XXAnalyzer,
    MI4XXCollector,
    MI4XXCollectorArgs,
    Mi4xxServiceabilityAnalyzerArgs,
    Mi4xxServiceabilityPlugin,
    ServiceabilityDataModel,
    ServiceabilityPluginBase,
    analyze_serviceability_window,
    default_afid_sag_path,
    load_hub_from_entry_point,
    resolve_configured_afid_sag_path,
    run_entry_point_hub,
    serviceability_block_from_entry_point_hub,
    validate_afid_sag_path,
)
from nodescraper.plugins.serviceability.mi4xx.mi4xx_event_log_paging import (
    fetch_mi4xx_event_log,
)
from nodescraper.plugins.serviceability.se_runner import HubRunError
from nodescraper.plugins.serviceability.serviceability_hub_analyzer import (
    AfidSagMetadataArtifact,
    ServiceabilityHubAnalyzer,
)


def _analyze_decorator_depth(func):
    depth = 0
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
        depth += 1
    return depth


def test_mi4xx_analyzer_analyze_data_wrapped_once():
    assert _analyze_decorator_depth(MI4XXAnalyzer.analyze_data) == 1
    assert MI4XXAnalyzer.analyze_data is ServiceabilityHubAnalyzer.analyze_data


class _FakeHub:
    name = "ExampleHub"

    def analyze(self, events, afid_sag_path):
        assert afid_sag_path
        assert events
        first = events[0] if isinstance(events, list) else events
        if isinstance(first, dict) and ("Oem" in first or "Id" in first):
            row = {
                "afid": DUMMY_AFID_A,
                "serviceable_unit": DUMMY_UNIT_A,
                "count": 1,
                "artifact": "redfish",
            }
        else:
            row = {
                "afid": first.get("afid", DUMMY_AFID_A),
                "serviceable_unit": first.get("location")
                or first.get("serviceable_unit", DUMMY_UNIT_A),
                "count": first.get("count", 1),
                "artifact": first.get("artifact", "cli"),
            }
        return {
            "schema_version": "1.0",
            "status": "ok",
            "error": None,
            "engine": self.name,
            "engine_version": DUMMY_HUB_VERSION_ENTRY,
            "results": [
                {
                    "afid_num": row["afid"],
                    "location": row.get("serviceable_unit") or row.get("location"),
                    "count": row.get("count", 1),
                    "artifact": row.get("artifact", "redfish"),
                    "tier": 1,
                    "tier_label": DUMMY_TIER_CRITICAL,
                    "service_action_num": DUMMY_SERVICE_ACTION_NUM,
                }
            ],
            "tier_grouped": {},
        }


def test_mi4xx_plugin_merge_afid_sag_path_into_args(tmp_path):
    sag = tmp_path / "custom_afid_sag.json"
    sag.write_text("{}", encoding="utf-8")

    collection_args, analysis_args = Mi4xxServiceabilityPlugin._merge_afid_sag_path(
        str(sag),
        None,
        None,
    )

    assert collection_args == {"afid_sag_path": str(sag)}
    assert analysis_args == {"afid_sag_path": str(sag)}


def test_mi4xx_plugin_merge_afid_sag_path_overrides_analysis_args(tmp_path):
    sag = tmp_path / "override_afid_sag.json"
    sag.write_text("{}", encoding="utf-8")

    _, analysis_args = Mi4xxServiceabilityPlugin._merge_afid_sag_path(
        str(sag),
        None,
        {"afid_sag_path": "/tmp/old_sag.json", "hub_entry_point": "hub"},
    )

    assert analysis_args == {
        "afid_sag_path": str(sag),
        "hub_entry_point": "hub",
    }


def test_mi4xx_collector_args_default_event_log_uri():
    args = MI4XXCollectorArgs()
    assert (
        args.resolved_event_log_uri()
        == Mi4xxServiceabilityAnalyzerArgs().resolved_rf_event_log_uri()
    )


def test_mi4xx_analyzer_args_default_event_log_uri():
    args = Mi4xxServiceabilityAnalyzerArgs()
    assert args.resolved_rf_event_log_uri() == (
        "/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries"
    )


def test_mi4xx_serviceability_plugin_wiring():
    assert issubclass(Mi4xxServiceabilityPlugin, ServiceabilityPluginBase)
    assert Mi4xxServiceabilityPlugin.COLLECTOR_ARGS is MI4XXCollectorArgs
    assert Mi4xxServiceabilityPlugin.ANALYZER_ARGS is Mi4xxServiceabilityAnalyzerArgs
    assert Mi4xxServiceabilityPlugin.ANALYZER is MI4XXAnalyzer


def test_mi4xx_analyzer_args_requires_hub_entry_point_in_config():
    args = Mi4xxServiceabilityAnalyzerArgs()
    assert args.hub_entry_point is None
    with pytest.raises(ValueError, match="hub_entry_point is required"):
        args.resolved_hub_entry_point()
    configured = Mi4xxServiceabilityAnalyzerArgs(hub_entry_point="hub")
    assert configured.resolved_hub_entry_point() == "hub"
    assert configured.skip_hub is False


def test_load_hub_from_entry_point():
    fake_ep = SimpleNamespace(name="hub", load=lambda: _FakeHub)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        hub = load_hub_from_entry_point("hub")
    assert hub.name == "ExampleHub"


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
    fake_ep = SimpleNamespace(name="hub", load=lambda: _FakeHub)
    events = [AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP)]
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        block = run_entry_point_hub(
            hub_entry_point="hub",
            afid_events=events,
            afid_sag_path=str(sag),
            rf_event_count=1,
        )
    assert block.hub_version == DUMMY_HUB_VERSION_ENTRY
    assert len(block.solution) == 1


def test_serviceability_block_from_entry_point_hub():
    events = [AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP)]
    block = serviceability_block_from_entry_point_hub(
        events,
        {
            "schema_version": "1.0",
            "status": "ok",
            "error": None,
            "engine": "ExampleHub",
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
            {
                "Afid": DUMMY_AFID_A,
                "ServiceableUnit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            }
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
            {
                "Afid": DUMMY_AFID_A,
                "ServiceableUnit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            }
        ]
    )
    fake_ep = SimpleNamespace(name="hub", load=lambda: _FakeHub)
    analyzer = MI4XXAnalyzer(system_info=system_info)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        task = analyzer.analyze_data(
            data,
            Mi4xxServiceabilityAnalyzerArgs(afid_sag_path=str(sag), hub_entry_point="hub"),
        )
    assert task.status == ExecutionStatus.OK
    assert "hub" in task.message.lower()


def test_mi4xx_analyzer_appends_afid_sag_metadata_artifact(system_info, tmp_path):
    sag = tmp_path / "afid_sag.json"
    sag.write_text('{"pid": "dummy-pid", "revision": "1"}', encoding="utf-8")
    data = ServiceabilityDataModel(
        rf_events=[
            {
                "Afid": DUMMY_AFID_A,
                "ServiceableUnit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            }
        ]
    )
    fake_ep = SimpleNamespace(name="hub", load=lambda: _FakeHub)
    analyzer = MI4XXAnalyzer(system_info=system_info)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        task = analyzer.analyze_data(
            data,
            Mi4xxServiceabilityAnalyzerArgs(afid_sag_path=str(sag), hub_entry_point="hub"),
        )
    assert task.status == ExecutionStatus.OK
    assert any(isinstance(artifact, AfidSagMetadataArtifact) for artifact in task.artifacts)


def test_mi4xx_plugin_analyzes_offline_data_without_collection(system_info, tmp_path):
    sag = tmp_path / "afid_sag.json"
    sag.write_text("{}", encoding="utf-8")
    data_path = tmp_path / "serviceability_data.json"
    data = ServiceabilityDataModel(
        rf_events=[
            {
                "Afid": DUMMY_AFID_A,
                "ServiceableUnit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            }
        ]
    )
    data_path.write_text(data.model_dump_json(), encoding="utf-8")
    fake_ep = SimpleNamespace(name="hub", load=lambda: _FakeHub)
    plugin = Mi4xxServiceabilityPlugin(system_info=system_info)
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[fake_ep],
    ):
        result = plugin.run(
            collection=False,
            analysis=True,
            data=str(data_path),
            analysis_args=Mi4xxServiceabilityAnalyzerArgs(
                afid_sag_path=str(sag), hub_entry_point="hub"
            ),
        )
    assert result.status == ExecutionStatus.OK
    assert result.result_data.analysis_result.status == ExecutionStatus.OK


def test_load_hub_from_entry_point_missing_raises():
    with patch(
        "nodescraper.plugins.serviceability.se_runner._entry_points_for_group",
        return_value=[],
    ):
        with pytest.raises(HubRunError, match="not found"):
            load_hub_from_entry_point("missing")


@pytest.fixture
def mi4xx_collector(system_info, redfish_conn_mock):
    redfish_conn_mock.base_url = f"https://{DUMMY_BMC_HOST}/redfish/v1"
    return MI4XXCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
        log_path="/tmp/serviceability.log",
    )


def test_fetch_mi4xx_event_log_follows_next_link(mi4xx_collector, redfish_conn_mock):
    page1_members = [{"Id": str(i)} for i in range(1000)]
    page2_members = [{"Id": str(i)} for i in range(1000, 1687)]
    next_link = "/redfish/v1/Systems/DummyAccelerators/LogServices/EventLog/Entries?$skip=1000"

    def run_get_side_effect(path: str, *_args, **_kwargs):
        if path == DUMMY_EVENT_URI:
            return RedfishGetResult(
                path=DUMMY_EVENT_URI,
                success=True,
                data={
                    RF_MEMBERS: page1_members,
                    RF_MEMBERS_COUNT: 1687,
                    RF_MEMBERS_NEXT_LINK: next_link,
                },
                status_code=200,
            )
        if path == next_link:
            return RedfishGetResult(
                path=next_link,
                success=True,
                data={RF_MEMBERS: page2_members},
                status_code=200,
            )
        raise AssertionError(f"unexpected path: {path}")

    redfish_conn_mock.run_get.side_effect = run_get_side_effect
    result = fetch_mi4xx_event_log(
        mi4xx_collector,
        DUMMY_EVENT_URI,
        max_pages=200,
    )
    assert result.success
    assert len(result.data[RF_MEMBERS]) == 1687
    assert RF_MEMBERS_NEXT_LINK not in result.data
    redfish_conn_mock.run_get_paged.assert_not_called()


def test_fetch_mi4xx_event_log_skip_fallback_when_no_next_link(mi4xx_collector, redfish_conn_mock):
    page1_members = [{"Id": str(i)} for i in range(1000)]
    page2_members = [{"Id": str(i)} for i in range(1000, 1200)]
    skip_uri = f"{DUMMY_EVENT_URI}?$skip=1000"

    def run_get_side_effect(path: str, *_args, **_kwargs):
        if path == DUMMY_EVENT_URI:
            return RedfishGetResult(
                path=DUMMY_EVENT_URI,
                success=True,
                data={
                    RF_MEMBERS: page1_members,
                    RF_MEMBERS_COUNT: 1200,
                },
                status_code=200,
            )
        if path == skip_uri:
            return RedfishGetResult(
                path=skip_uri,
                success=True,
                data={RF_MEMBERS: page2_members},
                status_code=200,
            )
        raise AssertionError(f"unexpected path: {path}")

    redfish_conn_mock.run_get.side_effect = run_get_side_effect
    result = fetch_mi4xx_event_log(
        mi4xx_collector,
        DUMMY_EVENT_URI,
        max_pages=200,
    )
    assert result.success
    assert len(result.data[RF_MEMBERS]) == 1200
    redfish_conn_mock.run_get_paged.assert_not_called()


def test_mi4xx_collector_collect_uses_mi4xx_paging_not_run_get_paged(
    mi4xx_collector, redfish_conn_mock
):
    members = [{"Id": "1"}, {"Id": "2"}]
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path=DUMMY_EVENT_URI,
        success=True,
        data={RF_MEMBERS: members, RF_MEMBERS_COUNT: 2},
        status_code=200,
    )
    args = MI4XXCollectorArgs(rf_event_log_uri=DUMMY_EVENT_URI, follow_next_link=True)
    result, data = mi4xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.rf_events) == 2
    redfish_conn_mock.run_get.assert_called()
    redfish_conn_mock.run_get_paged.assert_not_called()
