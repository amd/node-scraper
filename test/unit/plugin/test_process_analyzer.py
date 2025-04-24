import copy

import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.process.analyzer_args import ProcessAnalyzerArgs
from errorscraper.plugins.inband.process.process_analyzer import ProcessAnalyzer
from errorscraper.plugins.inband.process.processdata import ProcessDataModel


@pytest.fixture
def model_obj():
    return ProcessDataModel(
        kfd_process=0,
        cpu_usage=10,
        processes=[
            ("top", "10.0"),
            ("systemd", "0.0"),
            ("kthreadd", "0.0"),
            ("rcu_gp", "0.0"),
            ("rcu_par_gp", "0.0"),
        ],
    )


@pytest.fixture
def config():
    return {"max_kfd_processes": 0, "max_cpu_usage": 40}


@pytest.fixture
def analyzer(system_info):
    return ProcessAnalyzer(system_info=system_info)


def test_nominal_with_config(analyzer, model_obj, config):
    args = ProcessAnalyzerArgs(
        max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=config["max_cpu_usage"]
    )
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_nominal_no_config(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_error_kfd_process(analyzer, model_obj, config):
    modified_model_obj = copy.deepcopy(model_obj)
    modified_model_obj.kfd_process = 1
    args = ProcessAnalyzerArgs(
        max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=config["max_cpu_usage"]
    )
    result = analyzer.analyze_data(modified_model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.OS.value
        assert event.priority == EventPriority.CRITICAL


def test_error_cpu_usage(analyzer, model_obj, config):
    modified_model_obj = copy.deepcopy(model_obj)
    args = ProcessAnalyzerArgs(max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=5)
    result = analyzer.analyze_data(modified_model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.OS.value
        assert event.priority == EventPriority.CRITICAL
