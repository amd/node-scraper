import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.kernel_module.analyzer_args import (
    KernelModuleAnalyzerArgs,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_analyzer import (
    KernelModuleAnalyzer,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)


@pytest.fixture
def sample_modules():
    return {
        "modA": {"parameters": {"p": 1}},
        "otherMod": {"parameters": {"p": 2}},
        "TESTmod": {"parameters": {"p": 3}},
        "amdABC": {"parameters": {"p": 3}},
    }


@pytest.fixture
def data_model(sample_modules):
    return KernelModuleDataModel(kernel_modules=sample_modules)


@pytest.fixture
def analyzer(system_info):
    system_info.os_family = OSFamily.LINUX
    return KernelModuleAnalyzer(system_info=system_info)


def test_filter_modules_by_pattern_none(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, None)
    assert matched == sample_modules
    assert unmatched == []


def test_filter_modules_by_pattern_strict(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, [r"mod$"])
    assert set(matched) == {"otherMod", "TESTmod"}
    assert unmatched == []


def test_filter_modules_by_pattern_unmatched(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, ["foo"])
    assert matched == {}
    assert unmatched == ["foo"]


def test_filter_name_and_param_all_match(sample_modules, analyzer):
    to_match = {"modA": {"parameters": {"p": 1}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {"modA": sample_modules["modA"]}
    assert unmatched == {}


def test_filter_name_and_param_param_mismatch(sample_modules, analyzer):
    to_match = {"modA": {"parameters": {"p": 999}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {}
    assert "modA" in unmatched
    assert "p" in unmatched["modA"]["parameters"]


def test_filter_name_and_param_missing_module(sample_modules, analyzer):
    to_match = {"bogus": {"parameters": {"x": 1}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {}
    assert "bogus" in unmatched


def test_analyze_data_default(data_model, analyzer):
    result = analyzer.analyze_data(data_model, None)
    assert result.status == ExecutionStatus.OK


def test_analyze_data_regex_success(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_match=True, regex_filter=["^TESTmod$"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.OK
    ev = result.events[0]
    assert ev.description == "KernelModules analyzed"
    fm = ev.data["filtered_modules"]
    assert set(fm) == {"TESTmod"}


def test_analyze_data_regex_invalid_pattern(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_match=True, regex_filter=["*invalid"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.EXECUTION_FAILURE)
    assert any(EventCategory.RUNTIME.value in ev.category for ev in result.events)


def test_analyze_data_regex_unmatched_patterns(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_match=True, regex_filter=["modA", "nope"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.ERROR
    assert any(ev.description == "KernelModules did not match all patterns" for ev in result.events)


def test_analyze_data_name_only_success(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(
        regex_match=False, kernel_modules={"modA": {"parameters": {"p": 1}}}
    )
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "Kernel modules matched"
    assert result.events == []


def test_analyze_data_name_only_no_match(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_match=False, kernel_modules={"XYZ": {"parameters": {}}})
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.ERROR
    assert any("no modules matched" in ev.description.lower() for ev in result.events)


def test_analyze_data_name_only_partial_match(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(
        regex_match=False,
        kernel_modules={
            "modA": {"parameters": {"p": 1}},
            "otherMod": {"parameters": {"wrong": 0}},
        },
    )
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.ERROR
    assert any("not all modules matched" in ev.description.lower() for ev in result.events)
