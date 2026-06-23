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
import logging
import os
import tempfile

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.regex_search.analyzer_args import (
    RegexSearchAnalyzerArgs,
)
from nodescraper.plugins.inband.regex_search.regex_search_analyzer import (
    RegexSearchAnalyzer,
)
from nodescraper.plugins.inband.regex_search.regex_search_data import RegexSearchData
from nodescraper.plugins.inband.regex_search.regex_search_plugin import (
    RegexSearchPlugin,
)

EXPECTED_MISSING_ANALYSIS_MSG = "Analysis args need to be provided for the analyzer to run"


def test_regex_search_data_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("alpha\nbeta ERROR gamma\n")
        path = f.name
    try:
        data = RegexSearchData.import_model(path)
        assert "ERROR" in data.content
        assert os.path.basename(path) in data.files
        assert data.data_root == os.path.dirname(path)
    finally:
        os.unlink(path)


def test_regex_search_data_from_directory():
    with tempfile.TemporaryDirectory() as tmp:
        with open(f"{tmp}/a.txt", "w", encoding="utf-8") as f:
            f.write("one")
        with open(f"{tmp}/b.txt", "w", encoding="utf-8") as f:
            f.write("two")
        data = RegexSearchData.import_model(tmp)
        assert data.data_root == os.path.abspath(tmp)
        assert set(data.files.keys()) == {"a.txt", "b.txt"}
        assert data.files["a.txt"] == "one"
        assert data.files["b.txt"] == "two"
        assert "===== a.txt =====" in data.content
        assert "===== b.txt =====" in data.content


def test_regex_search_analyzer_match(system_info):
    data = RegexSearchData(content="line1\nFATAL: boom\nline3")
    analyzer = RegexSearchAnalyzer(system_info=system_info)
    args = RegexSearchAnalyzerArgs(
        error_regex=[{"regex": r"FATAL:.*", "message": "fatal seen"}],
    )
    result = analyzer.analyze_data(data, args)
    assert result.status == ExecutionStatus.ERROR
    assert "task detected errors" in result.message
    assert "fatal seen" in result.message
    assert len(result.events) == 1
    assert result.events[0].description == "fatal seen"


def test_regex_search_analyzer_missing_args(system_info):
    data = RegexSearchData(content="x")
    analyzer = RegexSearchAnalyzer(system_info=system_info)
    result = analyzer.analyze_data(data, None)
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == EXPECTED_MISSING_ANALYSIS_MSG

    result = analyzer.analyze_data(data, RegexSearchAnalyzerArgs(error_regex=None))
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == EXPECTED_MISSING_ANALYSIS_MSG

    result = analyzer.analyze_data(data, RegexSearchAnalyzerArgs(error_regex=[]))
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == EXPECTED_MISSING_ANALYSIS_MSG


def test_regex_search_plugin_missing_error_regex_not_ran_and_warning(
    system_info, logger, caplog, tmp_path
):
    log_file = tmp_path / "sample.log"
    log_file.write_text("line\n", encoding="utf-8")
    plugin = RegexSearchPlugin(system_info=system_info, logger=logger)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        out = plugin.run(
            collection=False,
            analysis=True,
            data=str(log_file),
            analysis_args=None,
        )
    assert out.result_data.analysis_result.status == ExecutionStatus.NOT_RAN
    assert out.result_data.analysis_result.message == EXPECTED_MISSING_ANALYSIS_MSG
    assert any(
        "analysis args need to be provided" in r.getMessage().lower() for r in caplog.records
    )


def test_regex_search_plugin_empty_analysis_args_dict_not_ran(system_info, logger, tmp_path):
    log_file = tmp_path / "sample.log"
    log_file.write_text("line\n", encoding="utf-8")
    plugin = RegexSearchPlugin(system_info=system_info, logger=logger)
    out = plugin.run(
        collection=False,
        analysis=True,
        data=str(log_file),
        analysis_args={},
    )
    assert out.result_data.analysis_result.status == ExecutionStatus.NOT_RAN
    assert out.result_data.analysis_result.message == EXPECTED_MISSING_ANALYSIS_MSG


def test_regex_search_plugin_no_data_warns_and_data_message(system_info, logger, caplog):
    plugin = RegexSearchPlugin(system_info=system_info, logger=logger)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        out = plugin.run(
            collection=False,
            analysis=True,
            data=None,
            analysis_args=None,
        )
    assert out.result_data.analysis_result.status == ExecutionStatus.NOT_RAN
    assert "No data available to analyze for RegexSearchPlugin" in (
        out.result_data.analysis_result.message
    )
    assert any(
        "analysis args need to be provided" in r.getMessage().lower() for r in caplog.records
    )


def test_regex_search_plugin_analyzer_only(system_info, logger):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("match_me_here\n")
        path = f.name
    try:
        plugin = RegexSearchPlugin(system_info=system_info, logger=logger)
        out = plugin.run(
            collection=False,
            analysis=True,
            data=path,
            analysis_args={
                "error_regex": [{"regex": r"match_me_here", "message": "found"}],
            },
        )
        assert out.status == ExecutionStatus.ERROR
        assert "Analysis error:" in out.message
        assert "found" in out.message
        assert out.result_data.analysis_result.status == ExecutionStatus.ERROR
        assert len(out.result_data.analysis_result.events) == 1
        desc = out.result_data.analysis_result.events[0].description
        assert "found" in desc
        assert "[file:" in desc
        assert path.replace("\\", "/") in desc.replace("\\", "/")
    finally:
        os.unlink(path)


def test_regex_search_multi_file_event_paths(system_info):
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "clean.log"), "w", encoding="utf-8").write("ok\n")
        open(os.path.join(tmp, "bad.log"), "w", encoding="utf-8").write("ERROR: boom\n")
        data = RegexSearchData.import_model(tmp)
        analyzer = RegexSearchAnalyzer(system_info=system_info)
        args = RegexSearchAnalyzerArgs(
            error_regex=[{"regex": r"ERROR[: ].*", "message": "err line"}],
        )
        result = analyzer.analyze_data(data, args)
        assert result.status == ExecutionStatus.ERROR
        assert len(result.events) == 1
        assert "err line" in result.events[0].description
        assert "[file:" in result.events[0].description
        assert "bad.log" in result.events[0].description
