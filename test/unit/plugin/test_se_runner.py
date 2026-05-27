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

import pytest
from pydantic import ValidationError

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
    run_service_engine,
    serviceability_block_from_service_result,
)
from nodescraper.plugins.serviceability.se_models import ServiceabilitySolution
from test.unit.plugin.serviceability_dummy_data import (
    DUMMY_AFID_A,
    DUMMY_AFID_B,
    DUMMY_AFID_C,
    DUMMY_DESIGNATION_A,
    DUMMY_DESIGNATION_B,
    DUMMY_ENGINE_VERSION,
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


def test_normalize_se_timestamp_preserves_engine_format():
    sample = "2000-01-01 12:00:00.000+00:00"
    assert normalize_se_timestamp(sample) == sample


def test_analyzer_args_require_engine_config():
    with pytest.raises(ValidationError):
        ServiceabilityAnalyzerArgs()
    with pytest.raises(ValidationError, match="engine_python_module"):
        ServiceabilityAnalyzerArgs(afid_sag_path=str(AFID_SAG))
    args = ServiceabilityAnalyzerArgs(
        engine_python_module="dummy.test.module",
        afid_sag_path=str(AFID_SAG),
    )
    assert args.engine_python_module == "dummy.test.module"


def test_format_serviceability_solution_lines():
    block = ServiceabilityBlock(
        afid_events=EXAMPLE_EVENTS[:1],
        solution=[
            ServiceabilitySolution(
                afid=DUMMY_AFID_A,
                serviceable_unit=[DUMMY_DESIGNATION_A, DUMMY_DESIGNATION_B],
                service_action_num=DUMMY_SERVICE_ACTION_NUM,
            )
        ],
        solution_reasoning="Dummy test reasoning.",
    )
    lines = format_serviceability_solution_lines(block)
    assert lines[0] == "Dummy test reasoning."
    assert f"AFID {DUMMY_AFID_A}" in lines[1]
    assert DUMMY_DESIGNATION_A in lines[1]


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
        engine_version_info={"version": DUMMY_ENGINE_VERSION},
    )
    block = serviceability_block_from_service_result(
        EXAMPLE_EVENTS[:1],
        result,
        engine_label="Dummy test engine",
        rf_event_count=DUMMY_RF_EVENT_COUNT,
    )
    assert len(block.solution) == 1
    assert block.solution[0].afid == DUMMY_AFID_A
    assert block.solution[0].service_action_num == DUMMY_SERVICE_ACTION_NUM
    assert set(block.solution[0].serviceable_unit) == {DUMMY_DESIGNATION_A, DUMMY_DESIGNATION_B}
    assert f"{DUMMY_RF_EVENT_COUNT} Redfish event(s)" in block.solution_reasoning
    assert "Dummy test engine" in block.solution_reasoning


def test_resolve_engine_class_finds_package_export():
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

    from nodescraper.plugins.serviceability.se_runner import _resolve_engine_class

    assert _resolve_engine_class(package) is submodule.EngineImpl


def test_run_service_engine_with_mock_module():
    rf_events = [
        {"Afid": DUMMY_AFID_A, "serviceable_unit": DUMMY_UNIT_A, "Created": DUMMY_TIMESTAMP},
        {"Afid": DUMMY_AFID_C, "serviceable_unit": DUMMY_UNIT_C, "Created": DUMMY_TIMESTAMP},
    ]
    block = run_service_engine(
        engine_python_module="test.unit.plugin.fixtures.mock_python_engine",
        afid_events=EXAMPLE_EVENTS[:2],
        afid_sag_path=str(AFID_SAG),
        rf_events=rf_events,
    )
    assert len(block.solution) == 2
    assert block.solution[0].afid == DUMMY_AFID_A
    assert block.solution[0].service_action_num == DUMMY_SERVICE_ACTION_NUM


def test_run_service_engine_missing_sag_raises():
    with pytest.raises(SeRunError, match="AFID_SAG"):
        run_service_engine(
            engine_python_module="test.unit.plugin.fixtures.mock_python_engine",
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


def test_mi3xx_analyzer_runs_python_engine(system_info):
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
        engine_python_module="test.unit.plugin.fixtures.mock_python_engine",
        afid_sag_path=str(AFID_SAG),
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
