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
from pydantic import ValidationError

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.generic_collection.analyzer_args import (
    CommandCheck,
    GenericAnalyzerArgs,
)
from nodescraper.plugins.inband.generic_collection.generic_analyzer import (
    GenericAnalyzer,
)
from nodescraper.plugins.inband.generic_collection.generic_collection_data import (
    CommandCollectionResult,
    GenericCollectionDataModel,
)


@pytest.fixture
def analyzer(system_info):
    return GenericAnalyzer(system_info=system_info)


def _data(*results: CommandCollectionResult) -> GenericCollectionDataModel:
    return GenericCollectionDataModel(results=list(results))


def test_evaluates_each_check_independently(analyzer):
    data = _data(
        CommandCollectionResult(
            name="kernel_os",
            command="uname -s",
            success=True,
            exit_code=0,
            stdout="Linux\n",
        ),
        CommandCollectionResult(
            name="messages",
            command="cat /var/log/messages",
            success=False,
            exit_code=1,
            stdout="",
            stderr="No such file",
        ),
        CommandCollectionResult(
            name="uid",
            command="id -u",
            success=True,
            exit_code=0,
            stdout="1000\n",
        ),
    )
    args = GenericAnalyzerArgs(
        checks=[
            CommandCheck(name="kernel_os", must_contain="TEST"),
            CommandCheck(name="messages", must_not_contain="error"),
            CommandCheck(name="uid", expected_regex=r"^\d+$"),
        ],
    )

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.ERROR
    assert "1/3 checks passed" in result.message


def test_must_contain_passes(analyzer):
    data = _data(
        CommandCollectionResult(
            name="kernel_os",
            command="uname -s",
            success=True,
            exit_code=0,
            stdout="Linux\n",
        )
    )
    args = GenericAnalyzerArgs(checks=[CommandCheck(name="kernel_os", must_contain="Linux")])

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.OK
    assert "1/1 checks passed" in result.message


def test_expected_value_numeric_compare(analyzer):
    data = _data(
        CommandCollectionResult(
            name="gpu_count",
            command="echo 8",
            success=True,
            exit_code=0,
            stdout="8\n",
        )
    )
    args = GenericAnalyzerArgs(
        checks=[
            CommandCheck(
                name="gpu_count",
                expected_value=8,
                compare_op="==",
                value_type="int",
            )
        ],
    )

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.OK


def test_expected_value_numeric_compare_fails(analyzer):
    data = _data(
        CommandCollectionResult(
            name="gpu_count",
            command="echo 4",
            success=True,
            exit_code=0,
            stdout="4\n",
        )
    )
    args = GenericAnalyzerArgs(
        checks=[
            CommandCheck(
                name="gpu_count",
                expected_value=8,
                compare_op="==",
                value_type="int",
            )
        ],
    )

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.ERROR


def test_line_count_checks(analyzer):
    data = _data(
        CommandCollectionResult(
            name="devices",
            command="lspci",
            success=True,
            exit_code=0,
            stdout="dev1\n\ndev2\n",
        )
    )
    args = GenericAnalyzerArgs(checks=[CommandCheck(name="devices", min_lines=2, max_lines=2)])

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.OK


def test_stdout_required_for_content_check(analyzer):
    data = _data(
        CommandCollectionResult(
            name="kernel_os",
            command="uname -s",
            success=True,
            exit_code=0,
            stdout=None,
        )
    )
    args = GenericAnalyzerArgs(checks=[CommandCheck(name="kernel_os", must_contain="Linux")])

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.ERROR


def test_allow_failure_passes_failed_command_check(analyzer):
    data = _data(
        CommandCollectionResult(
            name="optional",
            command="false",
            success=False,
            exit_code=1,
            stdout="",
        )
    )
    args = GenericAnalyzerArgs(
        checks=[CommandCheck(name="optional", allow_failure=True, expected_exit_code=1)],
    )

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.OK


def test_no_checks_reports_collection_summary(analyzer):
    data = _data(
        CommandCollectionResult(
            name="false_cmd",
            command="false",
            success=False,
            exit_code=1,
            stdout="",
        )
    )

    result = analyzer.analyze_data(data, GenericAnalyzerArgs(checks=[]))

    assert result.status == ExecutionStatus.OK
    assert "0/1 commands collected" in result.message


def test_analyzer_args_require_unique_check_names():
    with pytest.raises(ValidationError, match="Duplicate check name"):
        GenericAnalyzerArgs(
            checks=[
                CommandCheck(name="kernel_os", must_contain="Linux"),
                CommandCheck(name="kernel_os", expected="Linux"),
            ]
        )


def test_analyzer_args_require_check_name():
    with pytest.raises(ValidationError):
        GenericAnalyzerArgs(checks=[CommandCheck(name="", must_contain="Linux")])
