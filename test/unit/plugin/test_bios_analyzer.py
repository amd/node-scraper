import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.bios.analyzer_args import BiosAnalyzerArgs
from errorscraper.plugins.inband.bios.bios_analyzer import BiosAnalyzer
from errorscraper.plugins.inband.bios.biosdata import BiosDataModel


@pytest.fixture
def bios_model():
    return BiosDataModel(bios_version="RMP1004BS")


def test_nominal_with_config(bios_model, system_info):
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=["RMP1004BS"])
    res = analyzer.analyze_data(bios_model, args)
    assert res.status == ExecutionStatus.OK
    assert len(res.events) == 0


def test_single_string_exp_bios_version(bios_model, system_info):
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version="RMP1004BS")  # string instead of list
    res = analyzer.analyze_data(bios_model, args)
    assert res.status == ExecutionStatus.OK
    assert len(res.events) == 0


def test_no_config(bios_model, system_info):
   analyzer = BiosAnalyzer(system_info=system_info)
   res = analyzer.analyze_data(bios_model)  # No args passed
   assert res.status == ExecutionStatus.NOT_RAN
   assert len(res.events) == 0


def test_invalid_bios(system_info):
    model = BiosDataModel(bios_version="some_invalid_bios")
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=["RMP1004BS"])
    res = analyzer.analyze_data(model, args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].category == EventCategory.BIOS.value
    assert res.events[0].priority == EventPriority.ERROR


def test_unexpected_bios(system_info):
    model = BiosDataModel(bios_version="RMP1004BS")
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=["some_other_bios"])
    res = analyzer.analyze_data(model, args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].category == EventCategory.BIOS.value
    assert res.events[0].priority == EventPriority.ERROR


def test_bios_regex_match(system_info):
    model = BiosDataModel(bios_version="RMP1004BS")
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=[r"RMP\d{4}BS"], regex_match=True)
    res = analyzer.analyze_data(model, args)
    assert res.status == ExecutionStatus.OK
    assert len(res.events) == 0


def test_bios_regex_no_match(system_info):
    model = BiosDataModel(bios_version="RMP1004BS")
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=[r"RMP\d{3}BS"], regex_match=True)
    res = analyzer.analyze_data(model, args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].category == EventCategory.BIOS.value
    assert res.events[0].priority == EventPriority.ERROR


# Which node do we run on, whats the bios_version?
def test_invalid_regex(system_info):
    model = BiosDataModel(bios_version="RMP1004BS")
    analyzer = BiosAnalyzer(system_info=system_info)
    args = BiosAnalyzerArgs(exp_bios_version=[r"R[MP\d{4}B{S"], regex_match=True)
    res = analyzer.analyze_data(model, args)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 2
    assert res.events[0].category == EventCategory.BIOS.value
    assert res.events[0].priority == EventPriority.ERROR
    assert "Invalid regex pattern" in res.events[0].description
