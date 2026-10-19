###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from typing import Optional

from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.interfaces.dataanalyzertask import analyze_decorator
from nodescraper.models.event import Event
from nodescraper.models.taskresult import TaskResult


def test_invalid_data(mock_analyzer, dummy_data_model, system_info):
    @analyze_decorator
    def fake(self, data: dummy_data_model):
        self.result.status = ExecutionStatus.OK

    analyzer = mock_analyzer(system_info)
    result = fake(analyzer, data="NOT-DATAMODEL", args=None)

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert "Invalid data input" in result.message
    assert len(result.events) == 1
    event = result.events[0]
    assert event.category == "RUNTIME"
    assert event.priority == EventPriority.CRITICAL
    assert event.description == "Analyzer passed invalid data"


def test_success_no_args(mock_analyzer, dummy_data_model, dummy_arg, system_info):
    @analyze_decorator
    def fake(self, data: dummy_data_model, args: dummy_arg):
        self.result.status = ExecutionStatus.OK

    analyzer = mock_analyzer(system_info)
    model = dummy_data_model(foo=1)
    result = fake(analyzer, data=model, args=None)

    assert result.status == ExecutionStatus.OK


def test_success_with_args(mock_analyzer, dummy_data_model, dummy_arg, system_info):
    @analyze_decorator
    def fake_ok(self, data: dummy_data_model, args: dummy_arg):
        assert isinstance(args, dummy_arg)
        self.result.status = ExecutionStatus.OK

    model = dummy_data_model(foo=1)

    analyzer = mock_analyzer(system_info)
    result = fake_ok(analyzer, data=model, args={"value": 1})
    assert result.status == ExecutionStatus.OK
    assert analyzer.events == []

    analyzer = mock_analyzer(system_info)
    result = fake_ok(analyzer, data=model, args={"some_bad_field": 5})
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert len(result.events) == 1
    event = result.events[0]
    assert event.category == "RUNTIME"
    assert event.priority == EventPriority.CRITICAL
    assert "Validation error during analysis" in event.description

    @analyze_decorator
    def fake_err(self, data: dummy_data_model, args: dummy_arg):
        raise ValueError("some_err")

    analyzer = mock_analyzer(system_info)
    result = fake_err(analyzer, data=model, args={"value": 1})
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert any(
        "Exception during data analysis: some_err" in event.description for event in result.events
    )


def test_analyzer_subclass_with_none_data_model_raises_type_error(dummy_data_model):
    """Baseline: DATA_MODEL explicitly set to None is rejected with a TypeError."""
    import pytest

    from nodescraper.interfaces.dataanalyzertask import DataAnalyzer

    with pytest.raises(TypeError):

        class NoneModelAnalyzer(DataAnalyzer):
            DATA_MODEL = None

            def analyze_data(self, data, args=None):
                return self.result


def test_analyzer_subclass_without_data_model_raises_type_error():
    """A concrete analyzer that never declares DATA_MODEL must raise TypeError, not AttributeError."""
    import pytest

    from nodescraper.interfaces.dataanalyzertask import DataAnalyzer

    with pytest.raises(TypeError):

        class MissingModelAnalyzer(DataAnalyzer):
            def analyze_data(self, data, args=None):
                return self.result


def _event(priority: EventPriority, description: str, count: Optional[int] = None) -> Event:
    data = {"count": count} if count is not None else {}
    return Event(category="OS", description=description, priority=priority, data=data)


def test_event_summary_empty_when_no_events():
    assert TaskResult()._get_event_summary() == ""


def test_event_summary_counts_warnings_and_errors():
    result = TaskResult(
        events=[
            _event(EventPriority.WARNING, "w1"),
            _event(EventPriority.WARNING, "w2", count=2),
            _event(EventPriority.ERROR, "e1"),
        ]
    )
    assert result._get_event_summary() == "3 warnings; 1 errors: e1"


def test_event_summary_top_three_errors_by_count_with_omission_note():
    result = TaskResult(
        events=[
            _event(EventPriority.ERROR, "e1"),
            _event(EventPriority.ERROR, "e2", count=4),
            _event(EventPriority.ERROR, "e1"),
            _event(EventPriority.ERROR, "e3"),
            _event(EventPriority.ERROR, "e4"),
        ]
    )
    assert result._get_event_summary() == (
        "8 errors: e2 (x4), e1 (x2), e3 (omitted 1 descriptions)"
    )


def test_event_summary_critical_counted_as_error_and_listed():
    result = TaskResult(events=[_event(EventPriority.CRITICAL, "c1")])
    assert result._get_event_summary() == "1 errors; critical: c1"


def test_event_summary_three_critical_no_omission_note():
    result = TaskResult(events=[_event(EventPriority.CRITICAL, f"c{i}") for i in range(3)])
    summary = result._get_event_summary()
    assert summary == "3 errors; critical: c0, c1, c2"
    assert "omitted" not in summary


def test_event_summary_top_three_critical_by_count_with_omission_note():
    result = TaskResult(
        events=[
            _event(EventPriority.CRITICAL, "rare"),
            _event(EventPriority.CRITICAL, "common", count=5),
            _event(EventPriority.CRITICAL, "mid", count=3),
            _event(EventPriority.CRITICAL, "also_rare"),
            _event(EventPriority.CRITICAL, "second", count=4),
        ]
    )
    assert result._get_event_summary() == (
        "14 errors; critical: common (x5), second (x4), mid (x3) (omitted 2 descriptions)"
    )
