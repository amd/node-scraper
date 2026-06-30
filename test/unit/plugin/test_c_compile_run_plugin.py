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
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.inband.c_compile_run import (
    CCompileRunAnalyzer,
    CCompileRunAnalyzerArgs,
    CCompileRunCollector,
    CCompileRunCollectorArgs,
    CCompileRunDataModel,
    CCompileRunPlugin,
)
from nodescraper.plugins.inband.c_compile_run.c_compile_run_collector import (
    _build_compile_command,
    _build_run_command,
)
from nodescraper.plugins.inband.c_compile_run.c_compile_run_data import (
    CommandPhaseResult,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return CCompileRunCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_plugin_registered():
    registry = PluginRegistry()
    assert "CCompileRunPlugin" in registry.plugins
    assert registry.plugins["CCompileRunPlugin"] is CCompileRunPlugin


def test_collector_args_reject_non_c_source():
    with pytest.raises(ValidationError):
        CCompileRunCollectorArgs(source_path="/tmp/test.cpp")


def test_build_compile_command_with_extra_args():
    args = CCompileRunCollectorArgs(
        source_path="/tmp/hello.c",
        gcc_extra_args=["-Wall", "-O2"],
        output_path="/tmp/hello",
    )
    command = _build_compile_command(args, "/tmp/hello")
    assert command == "gcc -Wall -O2 -o /tmp/hello /tmp/hello.c"


def test_build_compile_command_static_lto():
    args = CCompileRunCollectorArgs(
        source_path="/path/to/test.c",
        output_path="/path/to/exe",
        gcc_extra_args=["-O3", "-static", "-flto", "-march=x86-64", "-s"],
    )
    command = _build_compile_command(args, "/path/to/exe")
    assert command == "gcc -O3 -static -flto -march=x86-64 -s -o /path/to/exe /path/to/test.c"


def test_collect_run_uses_run_sudo_only(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            CommandArtifact(exit_code=0, stdout="", stderr="", command="gcc ..."),
            CommandArtifact(exit_code=0, stdout="", stderr="", command="/path/to/exe"),
        ]
    )
    args = CCompileRunCollectorArgs(
        source_path="/path/to/test.c",
        output_path="/path/to/exe",
        gcc_extra_args=["-O3", "-static", "-flto", "-march=x86-64", "-s"],
        compile_sudo=False,
        run_sudo=True,
    )

    collector.collect_data(args)

    assert collector._run_sut_cmd.call_args_list[0].kwargs["sudo"] is False
    assert collector._run_sut_cmd.call_args_list[1].kwargs["sudo"] is True


def test_build_run_command_with_work_dir():
    args = CCompileRunCollectorArgs(
        source_path="/tmp/hello.c",
        work_dir="/tmp",
        run_args=["--verbose"],
    )
    command = _build_run_command(args, "/tmp/hello")
    assert command == "cd /tmp && /tmp/hello --verbose"


def test_collect_compile_and_run_success(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            CommandArtifact(
                exit_code=0,
                stdout="",
                stderr="",
                command="gcc -o /tmp/hello /tmp/hello.c",
            ),
            CommandArtifact(
                exit_code=0,
                stdout="ok\n",
                stderr="",
                command="/tmp/hello",
            ),
        ]
    )
    args = CCompileRunCollectorArgs(source_path="/tmp/hello.c")

    result, data = collector.collect_data(args)

    assert result.status == ExecutionStatus.OK
    assert data == CCompileRunDataModel(
        source_path="/tmp/hello.c",
        output_path="/tmp/hello",
        compile=CommandPhaseResult(
            command="gcc -o /tmp/hello /tmp/hello.c",
            exit_code=0,
            success=True,
            stdout="",
            stderr=None,
        ),
        run=CommandPhaseResult(
            command="/tmp/hello",
            exit_code=0,
            success=True,
            stdout="ok\n",
            stderr=None,
        ),
    )
    assert collector._run_sut_cmd.call_count == 2


def test_collect_skips_run_on_compile_failure(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=CommandArtifact(
            exit_code=1,
            stdout="",
            stderr="error",
            command="gcc -o /tmp/hello /tmp/hello.c",
        )
    )
    args = CCompileRunCollectorArgs(source_path="/tmp/hello.c")

    result, data = collector.collect_data(args)

    assert result.status == ExecutionStatus.ERROR
    assert data.run is None
    assert collector._run_sut_cmd.call_count == 1


def test_analyzer_flags_run_stdout_mismatch(system_info):
    analyzer = CCompileRunAnalyzer(system_info=system_info)
    data = CCompileRunDataModel(
        source_path="/tmp/hello.c",
        output_path="/tmp/hello",
        compile=CommandPhaseResult(command="gcc", exit_code=0, success=True),
        run=CommandPhaseResult(
            command="/tmp/hello",
            exit_code=0,
            success=True,
            stdout="unexpected\n",
        ),
    )

    result = analyzer.analyze_data(
        data,
        CCompileRunAnalyzerArgs(run_must_contain="expected"),
    )

    assert result.status == ExecutionStatus.ERROR
