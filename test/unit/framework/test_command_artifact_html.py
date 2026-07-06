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
from pathlib import Path

from nodescraper.command_artifact_html import render_command_artifacts_html
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.connection.redfish.redfish_connection import RedfishGetResult
from nodescraper.enums import SystemInteractionLevel
from nodescraper.models import CollectorArgs, TaskResult
from nodescraper.plugins.inband.switch.scale_out_arista.collector_args import (
    ScaleOutAristaCollectorArgs,
)
from nodescraper.plugins.inband.switch.scale_out_dell.collector_args import (
    ScaleOutDellCollectorArgs,
)
from nodescraper.plugins.inband.uptime.uptime_collector import UptimeCollector


def _command_artifact(result: TaskResult, index: int = 0) -> CommandArtifact:
    artifact = result.artifacts[index]
    assert isinstance(artifact, CommandArtifact)
    return artifact


def test_switch_collector_args_default_html_view_true():
    assert ScaleOutAristaCollectorArgs().html_view is True
    assert ScaleOutDellCollectorArgs().html_view is True


def test_switch_collector_applies_html_view_from_args(system_info, conn_mock):
    from nodescraper.base import InBandDataCollector
    from nodescraper.models.datamodel import DataModel

    class _SwitchDataModel(DataModel):
        value: str = ""

    class _SwitchCollector(InBandDataCollector[_SwitchDataModel, ScaleOutAristaCollectorArgs]):
        DATA_MODEL = _SwitchDataModel
        SUPPORTED_OS_FAMILY = {system_info.os_family}

        def collect_data(self, args=None):
            return self.result, None

    conn_mock.run_command.return_value = CommandArtifact(
        command="show version",
        stdout="EOS",
        stderr="",
        exit_code=0,
    )
    collector = _SwitchCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    collector.apply_collection_html_view(ScaleOutAristaCollectorArgs())
    collector._run_sut_cmd("show version")
    assert _command_artifact(collector.result).log_html is True


def test_render_command_artifacts_html_includes_command_and_output():
    html_doc = render_command_artifacts_html(
        [
            {
                "command": "show version",
                "stdout": "EOS 4.32",
                "stderr": "",
                "exit_code": 0,
            }
        ],
        "test_collector",
    )
    assert "show version" in html_doc
    assert "EOS 4.32" in html_doc
    assert "test_collector" in html_doc


def test_command_artifact_to_html_entry():
    artifact = CommandArtifact(
        command="uname -a",
        stdout="linux",
        stderr="",
        exit_code=0,
        log_html=True,
    )
    assert artifact.to_html_entry() == {
        "command": "uname -a",
        "stdout": "linux",
        "stderr": "",
        "exit_code": 0,
    }


def test_redfish_get_result_to_html_entry():
    artifact = RedfishGetResult(
        path="/redfish/v1/Systems",
        success=True,
        data={"Name": "System"},
        status_code=200,
        log_html=True,
    )
    entry = artifact.to_html_entry()
    assert entry["command"] == "GET /redfish/v1/Systems"
    assert '"Name"' in entry["stdout"]
    assert entry["exit_code"] == 0


def test_run_sut_cmd_defaults_html_view_false(system_info, conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        command="echo ok",
        stdout="ok",
        stderr="",
        exit_code=0,
    )
    collector = UptimeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )

    collector._run_sut_cmd("echo ok", log_artifact=True)
    assert len(collector.result.artifacts) == 1
    assert _command_artifact(collector.result).log_html is False

    collector.result = TaskResult()
    collector._run_sut_cmd("echo ok", log_artifact=False)
    assert collector.result.artifacts == []


def test_run_sut_cmd_html_view_without_log_artifact(system_info, conn_mock, tmp_path: Path):
    conn_mock.run_command.return_value = CommandArtifact(
        command="dmesg",
        stdout="log line",
        stderr="",
        exit_code=0,
    )
    collector = UptimeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    collector.result = TaskResult(task="dmesg_collector")

    collector._run_sut_cmd("dmesg", log_artifact=False, html_view=True)
    assert len(collector.result.artifacts) == 1
    assert _command_artifact(collector.result).log_html is True

    collector.result.log_result(str(tmp_path))
    assert (tmp_path / "command_artifacts.html").exists()
    html = (tmp_path / "command_artifacts.html").read_text(encoding="utf-8")
    assert "dmesg" in html
    assert "log line" in html


def test_collection_args_html_view(system_info, conn_mock, tmp_path: Path):
    from nodescraper.base import InBandDataCollector
    from nodescraper.models.datamodel import DataModel

    class _DataModel(DataModel):
        value: str = ""

    class _Collector(InBandDataCollector[_DataModel, CollectorArgs]):
        DATA_MODEL = _DataModel
        SUPPORTED_OS_FAMILY = {system_info.os_family}

        def collect_data(self, args=None):
            return self.result, None

    conn_mock.run_command.return_value = CommandArtifact(
        command="uptime",
        stdout="up 1 day",
        stderr="",
        exit_code=0,
    )
    collector = _Collector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    collector.apply_collection_html_view(CollectorArgs(html_view=True))
    collector.result = TaskResult(task="uptime_collector")
    collector._run_sut_cmd("uptime")
    assert _command_artifact(collector.result).log_html is True

    collector.result.log_result(str(tmp_path))
    assert (tmp_path / "command_artifacts.html").exists()


def test_log_result_skips_html_when_log_html_false(tmp_path: Path):
    result = TaskResult(task="package_collector")
    result.artifacts.append(
        CommandArtifact(
            command="rpm -qa",
            stdout="pkg-1",
            stderr="",
            exit_code=0,
            log_html=False,
        )
    )

    result.log_result(str(tmp_path))

    assert (tmp_path / "command_artifacts.json").exists()
    assert not (tmp_path / "command_artifacts.html").exists()
