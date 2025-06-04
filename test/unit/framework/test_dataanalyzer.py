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
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.interfaces.dataanalyzertask import analyze_decorator


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
