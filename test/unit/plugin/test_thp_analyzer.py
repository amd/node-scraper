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

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.inband.thp.analyzer_args import ThpAnalyzerArgs
from nodescraper.plugins.inband.thp.thp_analyzer import ThpAnalyzer
from nodescraper.plugins.inband.thp.thpdata import ThpDataModel


@pytest.fixture
def analyzer(system_info):
    return ThpAnalyzer(system_info=system_info)


@pytest.fixture
def sample_data():
    return ThpDataModel(enabled="always", defrag="madvise")


def test_analyzer_no_args_match(analyzer, sample_data):
    """No expected values -> OK."""
    result = analyzer.analyze_data(sample_data)
    assert result.status == ExecutionStatus.OK


def test_analyzer_match(analyzer, sample_data):
    """Expected values match -> OK."""
    args = ThpAnalyzerArgs(exp_enabled="always", exp_defrag="madvise")
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.OK


def test_analyzer_enabled_mismatch(analyzer, sample_data):
    """Expected enabled differs -> ERROR."""
    args = ThpAnalyzerArgs(exp_enabled="never")
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.ERROR
    assert "do not match" in result.message or "mismatch" in result.message.lower()


def test_analyzer_defrag_mismatch(analyzer, sample_data):
    """Expected defrag differs -> ERROR."""
    args = ThpAnalyzerArgs(exp_defrag="never")
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.ERROR


def test_build_from_model(sample_data):
    """build_from_model populates analyzer args from data model."""
    args = ThpAnalyzerArgs.build_from_model(sample_data)
    assert args.exp_enabled == "always"
    assert args.exp_defrag == "madvise"
