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
from nodescraper.plugins.inband.generic_collection.collector_args import (
    CommandSpec,
    GenericCollectionCollectorArgs,
)
from nodescraper.plugins.inband.generic_collection.generic_collection_collector import (
    GenericCollectionCollector,
)
from nodescraper.plugins.inband.generic_collection.generic_collection_data import (
    CommandCollectionResult,
    GenericCollectionDataModel,
)
from nodescraper.plugins.inband.generic_collection.generic_collection_plugin import (
    GenericCollectionPlugin,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return GenericCollectionCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_collect_all_commands_success(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            CommandArtifact(exit_code=0, stdout="linux\n", stderr="", command="uname -s"),
            CommandArtifact(exit_code=0, stdout="ok\n", stderr="", command="echo ok"),
        ]
    )
    args = GenericCollectionCollectorArgs(
        commands=[
            CommandSpec(name="kernel_os", command="uname -s"),
            CommandSpec(name="echo_ok", command="echo ok"),
        ]
    )

    result, data = collector.collect_data(args)

    assert result.status == ExecutionStatus.OK
    assert data == GenericCollectionDataModel(
        results=[
            CommandCollectionResult(
                name="kernel_os",
                command="uname -s",
                success=True,
                exit_code=0,
                sudo=False,
                stdout="linux\n",
            ),
            CommandCollectionResult(
                name="echo_ok",
                command="echo ok",
                success=True,
                exit_code=0,
                sudo=False,
                stdout="ok\n",
            ),
        ]
    )
    assert collector._run_sut_cmd.call_count == 2


def test_collect_reports_partial_failure(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            CommandArtifact(exit_code=0, stdout="linux\n", stderr="", command="uname -s"),
            CommandArtifact(exit_code=1, stdout="", stderr="failed", command="false"),
        ]
    )
    args = GenericCollectionCollectorArgs(
        commands=[
            CommandSpec(name="kernel_os", command="uname -s"),
            CommandSpec(name="false_cmd", command="false"),
        ]
    )

    result, data = collector.collect_data(args)

    assert result.status == ExecutionStatus.ERROR
    assert data.results[0].success is True
    assert data.results[1].success is False
    assert data.results[1].exit_code == 1
    assert data.results[1].stderr == "failed"


def test_collect_no_commands(collector):
    result, data = collector.collect_data(GenericCollectionCollectorArgs())

    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None


def test_collect_passes_global_sudo_and_timeout(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=CommandArtifact(exit_code=0, stdout="", stderr="", command="id")
    )
    args = GenericCollectionCollectorArgs(
        commands=[CommandSpec(name="user_id", command="id")],
        sudo=True,
        timeout=60,
    )

    collector.collect_data(args)

    collector._run_sut_cmd.assert_called_once_with("id", sudo=True, timeout=60)


def test_collect_per_command_sudo_overrides(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            CommandArtifact(exit_code=0, stdout="", stderr="", command="id"),
            CommandArtifact(exit_code=0, stdout="", stderr="", command="cat /var/log/messages"),
        ]
    )
    args = GenericCollectionCollectorArgs(
        commands=[
            CommandSpec(name="user_id", command="id"),
            CommandSpec(name="messages", command="cat /var/log/messages", sudo=True),
        ],
        sudo=False,
        timeout=300,
    )

    result, data = collector.collect_data(args)

    assert result.status == ExecutionStatus.OK
    assert collector._run_sut_cmd.call_args_list[0].kwargs == {"sudo": False, "timeout": 300}
    assert collector._run_sut_cmd.call_args_list[1].kwargs == {"sudo": True, "timeout": 300}
    assert data.results[0].sudo is False
    assert data.results[1].sudo is True


def test_collect_per_command_timeout_override(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=CommandArtifact(exit_code=0, stdout="", stderr="", command="sleep 1")
    )
    args = GenericCollectionCollectorArgs(
        commands=[CommandSpec(name="sleep_one", command="sleep 1", timeout=10)],
        timeout=300,
    )

    collector.collect_data(args)

    collector._run_sut_cmd.assert_called_once_with("sleep 1", sudo=False, timeout=10)


def test_collect_stores_stdout_when_disabled(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=CommandArtifact(
            exit_code=0, stdout="secret\n", stderr="", command="echo secret"
        )
    )
    args = GenericCollectionCollectorArgs(
        commands=[CommandSpec(name="secret", command="echo secret", include_stdout=False)],
        include_stdout=True,
    )

    _, data = collector.collect_data(args)

    assert data.results[0].stdout is None


def test_collector_args_reject_plain_string_commands():
    with pytest.raises(ValidationError, match="name' and 'command'"):
        GenericCollectionCollectorArgs(commands=["uname -s"])


def test_collector_args_require_name():
    with pytest.raises(ValidationError):
        GenericCollectionCollectorArgs(commands=[CommandSpec(name="", command="uname -s")])


def test_collector_args_require_unique_names():
    with pytest.raises(ValidationError, match="Duplicate command name"):
        GenericCollectionCollectorArgs(
            commands=[
                CommandSpec(name="dup", command="uname -s"),
                CommandSpec(name="dup", command="uname -m"),
            ]
        )


def test_generic_collection_plugin_wiring():
    assert GenericCollectionPlugin.DATA_MODEL is GenericCollectionDataModel
    assert GenericCollectionPlugin.get_collector_classes() == (GenericCollectionCollector,)
    assert GenericCollectionPlugin.COLLECTOR_ARGS is GenericCollectionCollectorArgs
    from nodescraper.plugins.inband.generic_collection.analyzer_args import (
        GenericAnalyzerArgs,
    )
    from nodescraper.plugins.inband.generic_collection.generic_analyzer import (
        GenericAnalyzer,
    )

    assert GenericCollectionPlugin.ANALYZER is GenericAnalyzer
    assert GenericCollectionPlugin.ANALYZER_ARGS is GenericAnalyzerArgs
