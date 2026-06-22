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
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_AFID_B,
    DUMMY_AFID_C,
    DUMMY_DESIGNATION_A,
    DUMMY_DESIGNATION_B,
    DUMMY_HUB_VERSION,
    DUMMY_OEM_VENDOR,
    DUMMY_RF_EVENT_COUNT,
    DUMMY_SAG_PID,
    DUMMY_SAG_REVISION,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_TIMESTAMP,
    DUMMY_UNIT_A,
    DUMMY_UNIT_B,
    DUMMY_UNIT_C,
)

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    AfidEvent,
    MI3XXAnalyzer,
    SeRunError,
    ServiceabilityAnalyzerArgs,
    ServiceabilityBlock,
    ServiceabilityDataModel,
    build_afid_events_from_data,
    format_serviceability_solution_lines,
    normalize_se_timestamp,
    run_service_hub,
    serviceability_block_from_service_result,
)
from nodescraper.plugins.serviceability.se_models import ServiceabilitySolution

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AFID_SAG = FIXTURES / "afid_sag_sample.json"
EXAMPLE_EVENTS = [
    AfidEvent(afid=DUMMY_AFID_A, serviceable_unit=DUMMY_UNIT_A, time=DUMMY_TIMESTAMP),
    AfidEvent(afid=DUMMY_AFID_B, serviceable_unit=DUMMY_UNIT_B, time=DUMMY_TIMESTAMP),
    AfidEvent(afid=DUMMY_AFID_C, serviceable_unit=DUMMY_UNIT_C, time=DUMMY_TIMESTAMP),
]


def test_afid_event_requires_non_empty_serviceable_unit():
    with pytest.raises(ValidationError):
        AfidEvent(afid=1, serviceable_unit="  ", time=DUMMY_TIMESTAMP)


def test_normalize_se_timestamp_preserves_format_value():
    sample = "2000-01-01 12:00:00.000+00:00"
    assert normalize_se_timestamp(sample) == sample


def test_analyzer_args_require_hub_config():
    with pytest.raises(ValidationError):
        ServiceabilityAnalyzerArgs()
    with pytest.raises(ValidationError, match="hub_python_module"):
        ServiceabilityAnalyzerArgs(afid_sag_path=str(AFID_SAG))
    args = ServiceabilityAnalyzerArgs(
        hub_python_module="dummy.test.module",
        afid_sag_path=str(AFID_SAG),
    )
    assert args.hub_python_module == "dummy.test.module"


def test_resolved_hub_options_explicit_fields_override_options_bag():
    args = ServiceabilityAnalyzerArgs(
        hub_python_module="dummy.test.module",
        afid_sag_path=str(AFID_SAG),
        hub_options={"from_ac_cycle": 9, "extra": 1},
        from_ac_cycle=3,
        from_date="2025-01-01",
        designation_serials={"U": "S"},
        suppress_service_actions=["99"],
    )
    merged = args.resolved_hub_options()
    assert merged["from_ac_cycle"] == 3
    assert merged["from_date"] == "2025-01-01"
    assert merged["designation_serials"] == {"U": "S"}
    assert merged["suppress_service_actions"] == ["99"]
    assert merged["extra"] == 1


def test_format_serviceability_solution_lines():
    block = ServiceabilityBlock(
        afid_events=EXAMPLE_EVENTS[:1],
        solution=[
            ServiceabilitySolution(
                afid=DUMMY_AFID_A,
                serviceable_unit=[DUMMY_DESIGNATION_A, DUMMY_DESIGNATION_B],
                service_action_num=DUMMY_SERVICE_ACTION_NUM,
                service_action_title="RMA",
            )
        ],
        solution_reasoning="Dummy test reasoning.",
        hub_version="1.0.0-test",
        afid_sag_file_version="PID sag-1, revision rev-a",
    )
    lines = format_serviceability_solution_lines(block)
    assert lines[0] == "Dummy test reasoning."
    assert lines[1] == "Hub version: 1.0.0-test"
    assert lines[2] == "AFID_SAG file: PID sag-1, revision rev-a"
    assert f"AFID {DUMMY_AFID_A}" in lines[3]
    assert DUMMY_DESIGNATION_A in lines[3]
    assert "service action 99 (RMA)" in lines[3]


def test_serviceability_block_from_service_result():
    result = SimpleNamespace(
        service_info={
            DUMMY_DESIGNATION_A: {
                str(DUMMY_AFID_A): {
                    "service_action_number": str(DUMMY_SERVICE_ACTION_NUM),
                    "error_category": "dummy_category",
                    "error_type": "dummy_type",
                    "title": "Dummy service action",
                }
            },
            DUMMY_DESIGNATION_B: {
                str(DUMMY_AFID_A): {
                    "service_action_number": str(DUMMY_SERVICE_ACTION_NUM),
                    "error_category": "dummy_category",
                    "error_type": "dummy_type",
                    "title": "Dummy service action",
                }
            },
        },
        afid_sag_metadata={"sag_pid": DUMMY_SAG_PID, "sag_revision": DUMMY_SAG_REVISION},
        engine_version_info={"version": DUMMY_HUB_VERSION},
    )
    block = serviceability_block_from_service_result(
        EXAMPLE_EVENTS[:1],
        result,
        hub_label="Dummy test hub",
        rf_event_count=DUMMY_RF_EVENT_COUNT,
    )
    assert len(block.solution) == 1
    assert block.solution[0].afid == DUMMY_AFID_A
    assert block.solution[0].service_action_num == DUMMY_SERVICE_ACTION_NUM
    assert block.solution[0].service_action_title == "Dummy service action"
    assert set(block.solution[0].serviceable_unit) == {DUMMY_DESIGNATION_A, DUMMY_DESIGNATION_B}
    assert block.hub_version == DUMMY_HUB_VERSION
    assert block.afid_sag_file_version is not None
    assert DUMMY_SAG_PID in block.afid_sag_file_version
    assert DUMMY_SAG_REVISION in block.afid_sag_file_version
    assert f"{DUMMY_RF_EVENT_COUNT} Redfish event(s)" in block.solution_reasoning
    assert "Dummy test hub" in block.solution_reasoning


def test_serviceability_block_from_service_result_isa_version_info():
    result = SimpleNamespace(
        service_info={},
        afid_sag_metadata={"sag_pid": DUMMY_SAG_PID, "sag_revision": DUMMY_SAG_REVISION},
        isa_version_info={"VERSION": "1.2.3"},
    )
    block = serviceability_block_from_service_result(
        EXAMPLE_EVENTS[:1],
        result,
        hub_label="ISA",
        rf_event_count=1,
    )
    assert block.hub_version == "1.2.3"
    assert block.afid_sag_file_version is not None
    assert DUMMY_SAG_PID in block.afid_sag_file_version


def test_resolve_hub_class_finds_package_export():
    import types

    submodule = types.ModuleType("fake_engine.impl")
    submodule.__dict__["EngineImpl"] = type(
        "EngineImpl",
        (),
        {"get_service_info": lambda self, rf_events, cper_data=None: None},
    )
    package = types.ModuleType("fake_engine")
    package.EngineImpl = submodule.EngineImpl  # type: ignore[attr-defined]
    package.__all__ = ["EngineImpl"]

    from nodescraper.plugins.serviceability.se_runner import _resolve_hub_class

    assert _resolve_hub_class(package) is submodule.EngineImpl


def test_run_service_hub_with_mock_module():
    rf_events = [
        {"Afid": DUMMY_AFID_A, "serviceable_unit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP},
        {"Afid": DUMMY_AFID_C, "serviceable_unit": DUMMY_UNIT_C, "Created": DUMMY_TIMESTAMP},
    ]
    block = run_service_hub(
        hub_python_module="mock_python_engine",
        afid_events=EXAMPLE_EVENTS[:2],
        afid_sag_path=str(AFID_SAG),
        rf_events=rf_events,
    )
    assert len(block.solution) == 2
    assert block.solution[0].afid == DUMMY_AFID_A
    assert block.solution[0].service_action_num == DUMMY_SERVICE_ACTION_NUM


def test_run_service_hub_custom_analyze_method_and_path_kwarg():
    import sys
    import types

    init_log: list[tuple[str, bool]] = []
    analyze_log: list[Any] = []

    class AltEngine:
        def __init__(self, rulebook_path: str, debug: bool = False) -> None:
            init_log.append((rulebook_path, debug))

        def analyze_events(self, rf_events, cper_data=None):
            analyze_log.append((list(rf_events), cper_data))
            return None

    mod = types.ModuleType("alt_service_engine")
    mod.AltEngine = AltEngine
    mod.__all__ = ["AltEngine"]
    sys.modules["alt_service_engine"] = mod
    try:
        run_service_hub(
            hub_python_module="alt_service_engine",
            afid_events=EXAMPLE_EVENTS[:1],
            afid_sag_path=str(AFID_SAG),
            rf_events=[{"Afid": 1}],
            cper_data={"k": 1},
            hub_options={"debug": True},
            hub_analyze_method="analyze_events",
            hub_init_path_kwarg="rulebook_path",
        )
    finally:
        del sys.modules["alt_service_engine"]

    assert init_log[0][0] == str(AFID_SAG)
    assert init_log[0][1] is True
    assert analyze_log[0][1] == {"k": 1}


def test_run_service_hub_accepts_hub_options():
    rf_events = [
        {"Afid": DUMMY_AFID_A, "serviceable_unit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP},
    ]
    block = run_service_hub(
        hub_python_module="mock_python_engine",
        afid_events=EXAMPLE_EVENTS[:1],
        afid_sag_path=str(AFID_SAG),
        rf_events=rf_events,
        hub_options={"reporting_level": "verbose"},
    )
    assert len(block.solution) == 1


def test_run_service_hub_forwards_full_hub_options_kwargs():
    from instinct_shaped_engine import clear_last_call, get_last_call

    clear_last_call()
    rf_events = [
        {"Afid": DUMMY_AFID_A, "serviceable_unit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP},
    ]
    run_service_hub(
        hub_python_module="instinct_shaped_engine",
        afid_events=EXAMPLE_EVENTS[:1],
        afid_sag_path=str(AFID_SAG),
        rf_events=rf_events,
        cper_data={"decoded": True},
        hub_options={
            "from_ac_cycle": 2,
            "from_date": "2024-06-01",
            "designation_serials": {"GPU0": "SN1"},
            "suppress_service_actions": ["42"],
        },
    )
    got = get_last_call()
    assert got["from_ac_cycle"] == 2
    assert got["from_date"] == "2024-06-01"
    assert got["cper_data"] == {"decoded": True}
    assert got["designation_serials"] == {"GPU0": "SN1"}
    assert got["suppress_service_actions"] == ["42"]


def test_run_service_hub_collected_cper_overrides_hub_options_cper_data():
    from instinct_shaped_engine import clear_last_call, get_last_call

    clear_last_call()
    rf_events = [
        {"Afid": DUMMY_AFID_A, "serviceable_unit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP},
    ]
    run_service_hub(
        hub_python_module="instinct_shaped_engine",
        afid_events=EXAMPLE_EVENTS[:1],
        afid_sag_path=str(AFID_SAG),
        rf_events=rf_events,
        cper_data={"from_collector": 1},
        hub_options={"cper_data": {"from_options": 2}, "from_ac_cycle": 0},
    )
    assert get_last_call()["cper_data"] == {"from_collector": 1}


def test_run_service_hub_missing_sag_raises():
    with pytest.raises(SeRunError, match="Hub config file not found"):
        run_service_hub(
            hub_python_module="mock_python_engine",
            afid_events=EXAMPLE_EVENTS,
            afid_sag_path="/nonexistent/dummy_afid_sag.json",
            rf_events=[{"Afid": DUMMY_AFID_A}],
        )


def test_build_afid_events_from_rf_members():
    data = ServiceabilityDataModel(
        rf_events=[
            {
                "Afid": DUMMY_AFID_A,
                "serviceable_unit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            },
            {
                "Oem": {
                    DUMMY_OEM_VENDOR: {
                        "Afid": DUMMY_AFID_B,
                        "serviceable_unit": DUMMY_UNIT_B,
                    }
                },
                "EventTimestamp": DUMMY_TIMESTAMP,
            },
        ]
    )
    events = build_afid_events_from_data(data)
    assert len(events) == 2
    assert events[0].afid == DUMMY_AFID_A
    assert events[1].afid == DUMMY_AFID_B


def test_mi3xx_analyzer_runs_python_hub(system_info):
    data = ServiceabilityDataModel(
        rf_events=[
            {
                "Afid": DUMMY_AFID_A,
                "serviceable_unit": DUMMY_UNIT_A,
                "Created": DUMMY_TIMESTAMP,
            },
            {
                "Afid": DUMMY_AFID_C,
                "serviceable_unit": DUMMY_UNIT_C,
                "Created": DUMMY_TIMESTAMP,
            },
        ]
    )
    analyzer = MI3XXAnalyzer(system_info=system_info)
    args = ServiceabilityAnalyzerArgs(
        hub_python_module="mock_python_engine",
        afid_sag_path=str(AFID_SAG),
        hub_options={"include_raw_events": False},
    )
    result = analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.OK
    assert data.serviceability is not None
    assert len(data.serviceability.solution) == 2


def test_mi3xx_analyzer_writes_serviceability_json(tmp_path, system_info):
    data = ServiceabilityDataModel(
        afid_events=EXAMPLE_EVENTS[:1],
        serviceability=ServiceabilityBlock(
            afid_events=EXAMPLE_EVENTS[:1],
            solution=[],
        ),
    )
    data.log_model(str(tmp_path))
    payload = json.loads((tmp_path / "serviceability.json").read_text(encoding="utf-8"))
    assert payload["afid_events"][0]["afid"] == DUMMY_AFID_A
