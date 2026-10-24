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
import abc
import json
import logging
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from framework.common.shared_utils import DummyDataModel, MockConnectionManager
from pydantic import BaseModel

from nodescraper.base.oobsshdataplugin import OOBSSHDataPlugin
from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.oob_ssh import OobSshConnectionManager
from nodescraper.enums import ExecutionStatus, OSFamily, SystemLocation
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces import (
    DataPlugin,
    PluginInterface,
    PluginResultCollator,
    TaskResultHook,
)
from nodescraper.interfaces.datacollectortask import DataCollector
from nodescraper.models import PluginConfig, PluginResult, SystemInfo, TaskResult
from nodescraper.models.postactioncondition import PostActionCondition
from nodescraper.models.postactionpluginconfig import PostActionPluginConfig
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.utils import resolve_log_dir_name


class DummyArgs(BaseModel):
    foo: str = "bar"
    regex_match: bool = True


class TestPluginA(PluginInterface[MockConnectionManager, None]):
    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = MockConnectionManager
    COLLECTOR_ARGS = DummyArgs(foo="initial")
    ANALYZER_ARGS = DummyArgs(foo="initial")
    collection = False
    analysis = False
    data = DummyDataModel(some_version="1")
    max_event_priority_level = EventPriority.INFO
    system_interaction_level = SystemInteractionLevel.PASSIVE
    collection_args = None

    def run(self):
        self._update_queue(("TestPluginB", {}))
        return PluginResult(source="testA", status=ExecutionStatus.ERROR)


class TestPluginB(PluginInterface[MockConnectionManager, None]):
    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = MockConnectionManager

    def run(self, test_arg=None):
        return PluginResult(
            source="testB", status=ExecutionStatus.OK, result_data={"arg_val": test_arg}
        )


class PostActionPlugin(PluginInterface[MockConnectionManager, None]):
    """Minimal plugin used as a post-action target in tests."""

    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = MockConnectionManager

    def run(self, **kwargs):
        return PluginResult(source="PostActionPlugin", status=ExecutionStatus.OK)


class TestPluginCapture(PluginInterface[MockConnectionManager, None]):
    """Records kwargs passed to run() for merge-order regression tests."""

    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = MockConnectionManager
    last_run_kwargs: Optional[dict] = None

    def run(self, **kwargs):
        TestPluginCapture.last_run_kwargs = kwargs
        return PluginResult(source="TestPluginCapture", status=ExecutionStatus.OK)


@pytest.fixture
def plugin_registry():
    registry = PluginRegistry()
    registry.plugins = {
        "TestPluginA": TestPluginA,
        "TestPluginB": TestPluginB,
        "PostActionPlugin": PostActionPlugin,
    }
    registry.connection_managers = {"MockConnectionManager": MockConnectionManager}
    return registry


@pytest.mark.parametrize(
    "input_configs, output_config",
    [
        (
            [PluginConfig(plugins={"Plugin1": {}}), PluginConfig(plugins={"Plugin2": {}})],
            PluginConfig(plugins={"Plugin1": {}, "Plugin2": {}}),
        ),
        (
            [
                PluginConfig(plugins={"Plugin1": {"arg1": "val1", "argA": "valA"}}),
                PluginConfig(plugins={"Plugin1": {"arg1": "val2"}}),
            ],
            # Deep merge: later config's keys override, existing keys preserved.
            PluginConfig(plugins={"Plugin1": {"arg1": "val2", "argA": "valA"}}),
        ),
        (
            [
                PluginConfig(global_args={"test": 123}),
                PluginConfig(global_args={"test1": "abc"}),
            ],
            PluginConfig(global_args={"test": 123, "test1": "abc"}),
        ),
    ],
)
def test_config_merge(input_configs: list[PluginConfig], output_config: PluginConfig):
    assert PluginExecutor.merge_configs(input_configs) == output_config


def test_plugin_executor_rejects_invalid_session_id():
    with pytest.raises(ValueError, match="session_id must be a valid UUID"):
        PluginExecutor(plugin_configs=[], session_id="not-a-uuid")


def test_plugin_queue(plugin_registry):
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(global_args={"test_arg": "abc"}, plugins={"TestPluginB": {}})],
        plugin_registry=plugin_registry,
    )

    results = executor.run_queue()

    assert len(results) == 1
    assert results[0].source == "testB"
    assert results[0].status == ExecutionStatus.OK
    assert results[0].result_data == {"arg_val": "abc"}


def test_queue_callback(plugin_registry):
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={"TestPluginA": {}})],
        plugin_registry=plugin_registry,
    )

    results = executor.run_queue()

    assert len(results) == 2
    assert results[0].source == "testA"
    assert results[0].status == ExecutionStatus.ERROR
    assert results[1].source == "testB"
    assert results[1].status == ExecutionStatus.OK


def test_merge_plugin_run_args_plugin_overrides_global():
    global_run_args = {
        "system_interaction_level": "INTERACTIVE",
        "collection_args": {"foo": "global", "shared": "global"},
        "analysis_args": {"bar": "global"},
    }
    plugin_args = {
        "system_interaction_level": "PASSIVE",
        "collection_args": {"foo": "plugin"},
    }

    merged = PluginExecutor.merge_plugin_run_args(plugin_args, global_run_args)

    assert merged["system_interaction_level"] == "PASSIVE"
    assert merged["collection_args"] == {"foo": "plugin", "shared": "global"}
    assert merged["analysis_args"] == {"bar": "global"}


@pytest.mark.parametrize(
    "plugin_args,global_run_args,expected_key,expected_value",
    [
        (
            {"system_interaction_level": SystemInteractionLevel.PASSIVE},
            {"system_interaction_level": SystemInteractionLevel.INTERACTIVE},
            "system_interaction_level",
            SystemInteractionLevel.PASSIVE,
        ),
        (
            {"system_interaction_level": "PASSIVE"},
            {"system_interaction_level": "INTERACTIVE"},
            "system_interaction_level",
            "PASSIVE",
        ),
        (
            {"analysis": False, "collection": True},
            {"analysis": True, "collection": True},
            "analysis",
            False,
        ),
        (
            {},
            {"system_interaction_level": SystemInteractionLevel.INTERACTIVE},
            "system_interaction_level",
            SystemInteractionLevel.INTERACTIVE,
        ),
    ],
)
def test_merge_plugin_run_args_plugin_wins_on_conflict(
    plugin_args, global_run_args, expected_key, expected_value
):
    merged = PluginExecutor.merge_plugin_run_args(plugin_args, global_run_args)
    assert merged[expected_key] == expected_value


def test_merge_plugin_run_args_analysis_args_plugin_overrides_global():
    merged = PluginExecutor.merge_plugin_run_args(
        {"analysis_args": {"exp_speed": 4, "shared": "plugin"}},
        {"analysis_args": {"exp_speed": 5, "shared": "global", "exp_width": 16}},
    )
    assert merged["analysis_args"] == {
        "exp_speed": 4,
        "shared": "plugin",
        "exp_width": 16,
    }


def test_run_queue_plugin_system_interaction_level_overrides_global(plugin_registry):
    """Per-plugin run() kwargs must win over global_args (PciePlugin PASSIVE case)."""
    plugin_registry.plugins["TestPluginCapture"] = TestPluginCapture
    TestPluginCapture.last_run_kwargs = None

    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                global_args={"system_interaction_level": SystemInteractionLevel.INTERACTIVE},
                plugins={
                    "TestPluginCapture": {
                        "system_interaction_level": SystemInteractionLevel.PASSIVE,
                    }
                },
            )
        ],
        plugin_registry=plugin_registry,
    )
    results = executor.run_queue()

    assert len(results) == 1
    assert results[0].source == "TestPluginCapture"
    assert TestPluginCapture.last_run_kwargs is not None
    assert (
        TestPluginCapture.last_run_kwargs["system_interaction_level"]
        == SystemInteractionLevel.PASSIVE
    )


def test_apply_global_args_to_plugin():
    plugin = TestPluginA()
    global_args = {
        "collection": True,
        "analysis": True,
        "data": {"some_version": "1"},
        "max_event_priority_level": 4,
        "system_interaction_level": "INTERACTIVE",
        "collection_args": {"foo": "collected", "regex_match": False, "not_in_model": "skip_this"},
        "analysis_args": {"foo": "analyzed", "regex_match": False, "ignore_this": True},
    }

    executor = PluginExecutor(plugin_configs=[])
    run_payload = executor.apply_global_args_to_plugin(plugin, TestPluginA, global_args)

    assert run_payload["collection"] is True
    assert run_payload["analysis"] is True
    assert run_payload["data"]["some_version"] == "1"
    assert run_payload["max_event_priority_level"] == 4
    assert run_payload["system_interaction_level"] == "INTERACTIVE"

    # Safely check filtered args
    assert run_payload.get("collection_args") == {
        "foo": "collected",
        "regex_match": False,
    }
    assert run_payload.get("analysis_args") == {
        "foo": "analyzed",
        "regex_match": False,
    }


def test_connection_manager_from_plugin_when_not_in_registry():
    """CONNECTION_TYPE may come from an external package without a registry entry."""
    registry = PluginRegistry()
    registry.plugins = {"TestPluginB": TestPluginB}
    registry.connection_managers = {}

    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={"TestPluginB": {}})],
        plugin_registry=registry,
    )
    results = executor.run_queue()

    assert len(results) == 1
    assert results[0].source == "testB"
    assert results[0].status == ExecutionStatus.OK


def test_plugin_run_result_hooks_called_after_each_plugin(plugin_registry):
    seen: list[str] = []

    def hook(res: PluginResult) -> None:
        seen.append(res.source)

    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={"TestPluginB": {}})],
        plugin_registry=plugin_registry,
        plugin_run_result_hooks=[hook],
    )
    executor.run_queue()
    assert seen == ["testB"]


# ---------------------------------------------------------------------------
# merge_configs: post_action_plugins concatenation
# ---------------------------------------------------------------------------


def test_merge_configs_concatenates_post_action_plugins():
    """post_action_plugins lists from multiple configs are concatenated."""
    pa1 = PostActionPluginConfig(
        plugin="PostActionPlugin",
        conditions=[PostActionCondition(status="ERROR")],
    )
    pa2 = PostActionPluginConfig(
        plugin="PostActionPlugin",
        conditions=[PostActionCondition(status="WARNING")],
    )
    configs = [
        PluginConfig(post_action_plugins=[pa1]),
        PluginConfig(post_action_plugins=[pa2]),
    ]
    merged = PluginExecutor.merge_configs(configs)
    assert len(merged.post_action_plugins) == 2
    assert merged.post_action_plugins[0] is pa1
    assert merged.post_action_plugins[1] is pa2


def test_merge_configs_empty_post_action_plugins():
    """Merging configs with no post_action_plugins yields an empty list."""
    configs = [PluginConfig(plugins={"TestPluginB": {}})]
    merged = PluginExecutor.merge_configs(configs)
    assert merged.post_action_plugins == []


def test_plugin_config_merge_concatenates_post_action_plugins():
    """PluginConfig.merge() (recipe merge) also concatenates post_action_plugins."""
    pa1 = PostActionPluginConfig(
        plugin="PostActionPlugin",
        conditions=[PostActionCondition(status="ERROR")],
    )
    pa2 = PostActionPluginConfig(
        plugin="PostActionPlugin",
        conditions=[PostActionCondition(status="WARNING")],
    )
    merged = PluginConfig.merge(
        PluginConfig(plugins={"TestPluginA": {}}, post_action_plugins=[pa1]),
        PluginConfig(plugins={"TestPluginB": {}}, post_action_plugins=[pa2]),
    )
    # Plugins from both configs are present
    assert "TestPluginA" in merged.plugins
    assert "TestPluginB" in merged.plugins
    # Post-action plugins from both configs are concatenated
    assert len(merged.post_action_plugins) == 2
    assert merged.post_action_plugins[0] is pa1
    assert merged.post_action_plugins[1] is pa2


def test_plugin_config_merge_empty_post_action_plugins():
    """PluginConfig.merge() with no post_action_plugins yields an empty list."""
    merged = PluginConfig.merge(
        PluginConfig(plugins={"TestPluginA": {}}),
        PluginConfig(plugins={"TestPluginB": {}}),
    )
    assert merged.post_action_plugins == []


# ---------------------------------------------------------------------------
# run_queue: post-action execution
# ---------------------------------------------------------------------------


def test_post_action_runs_when_condition_met(plugin_registry):
    """Post-action plugin fires when primary result meets the condition.

    TestPluginA returns ERROR and also queues TestPluginB via _update_queue,
    so the primary run produces two results (testA + testB).  The post-action
    fires on the ERROR status, giving a total of 3 results.
    """
    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                plugins={"TestPluginA": {}},  # TestPluginA always returns ERROR
                post_action_plugins=[
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        conditions=[PostActionCondition(status="ERROR")],
                    )
                ],
            )
        ],
        plugin_registry=plugin_registry,
    )
    results = executor.run_queue()

    sources = [r.source for r in results]
    assert "testA" in sources
    assert "testB" in sources  # queued by TestPluginA via _update_queue
    assert "PostActionPlugin" in sources
    assert len(results) == 3


def test_post_action_does_not_run_when_condition_not_met(plugin_registry):
    """Post-action plugin is skipped when no primary result meets the condition."""
    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                plugins={"TestPluginB": {}},  # TestPluginB always returns OK
                post_action_plugins=[
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        conditions=[PostActionCondition(status="ERROR")],
                    )
                ],
            )
        ],
        plugin_registry=plugin_registry,
    )
    results = executor.run_queue()

    assert len(results) == 1
    assert results[0].source == "testB"


def test_post_action_result_appended_to_run_queue_return(plugin_registry):
    """The post-action PluginResult is present in the list returned by run_queue()."""
    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                plugins={"TestPluginA": {}},
                post_action_plugins=[
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        conditions=[PostActionCondition(status="ERROR")],
                    )
                ],
            )
        ],
        plugin_registry=plugin_registry,
    )
    results = executor.run_queue()

    post_action_results = [r for r in results if r.source == "PostActionPlugin"]
    assert len(post_action_results) == 1
    assert post_action_results[0].status == ExecutionStatus.OK


def test_post_action_result_hooks_called(plugin_registry):
    """plugin_run_result_hooks are invoked for post-action results too."""
    seen: list[str] = []

    def hook(res: PluginResult) -> None:
        seen.append(res.source)

    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                plugins={"TestPluginA": {}},
                post_action_plugins=[
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        conditions=[PostActionCondition(status="ERROR")],
                    )
                ],
            )
        ],
        plugin_registry=plugin_registry,
        plugin_run_result_hooks=[hook],
    )
    executor.run_queue()

    assert "testA" in seen
    assert "PostActionPlugin" in seen


def test_multiple_post_actions_selective_firing(plugin_registry):
    """With two post-actions, only the one whose condition is met runs.

    testA returns ERROR (value=40).  The first condition requires ERROR (40 >= 40) → fires.
    The second condition requires EXECUTION_FAILURE (50); ERROR (40) < 50 → does not fire.
    """
    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(
                plugins={"TestPluginA": {}},  # returns ERROR
                post_action_plugins=[
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        conditions=[PostActionCondition(status="ERROR")],  # fires: ERROR >= ERROR
                    ),
                    PostActionPluginConfig(
                        plugin="PostActionPlugin",
                        # does not fire: testA is ERROR (40) < EXECUTION_FAILURE (50)
                        conditions=[
                            PostActionCondition(plugin="testA", status="EXECUTION_FAILURE")
                        ],
                    ),
                ],
            )
        ],
        plugin_registry=plugin_registry,
    )
    results = executor.run_queue()

    post_action_results = [r for r in results if r.source == "PostActionPlugin"]
    assert len(post_action_results) == 1  # only first post-action fired


def test_post_action_invalid_plugin_name_logs_error_and_continues(plugin_registry, caplog):
    """An unregistered post-action plugin name is logged as an error; run completes."""
    with caplog.at_level(logging.ERROR):
        executor = PluginExecutor(
            plugin_configs=[
                PluginConfig(
                    plugins={"TestPluginA": {}},
                    post_action_plugins=[
                        PostActionPluginConfig(
                            plugin="NonExistentPlugin",
                            conditions=[PostActionCondition(status="ERROR")],
                        )
                    ],
                )
            ],
            plugin_registry=plugin_registry,
        )
        results = executor.run_queue()

    # Primary result still returned; no exception raised
    assert any(r.source == "testA" for r in results)
    assert any("NonExistentPlugin" in record.message for record in caplog.records)


def test_closing_connections_logged_after_post_actions(plugin_registry, caplog):
    """'Closing connections' log appears after the post-action run log, not before."""
    with caplog.at_level(logging.INFO):
        executor = PluginExecutor(
            plugin_configs=[
                PluginConfig(
                    plugins={"TestPluginA": {}},
                    post_action_plugins=[
                        PostActionPluginConfig(
                            plugin="PostActionPlugin",
                            conditions=[PostActionCondition(status="ERROR")],
                        )
                    ],
                )
            ],
            plugin_registry=plugin_registry,
        )
        executor.run_queue()

    messages = [r.message for r in caplog.records]

    post_action_idx = next(
        (i for i, m in enumerate(messages) if "post-action plugin" in m.lower()), None
    )
    closing_idx = next(
        (i for i, m in enumerate(messages) if "closing connections" in m.lower()), None
    )

    assert post_action_idx is not None, "Expected a post-action log message"
    assert closing_idx is not None, "Expected a 'Closing connections' log message"
    assert (
        post_action_idx < closing_idx
    ), "'Closing connections' must be logged after the post-action plugin runs"


def test_discover_os_info_detects_linux(system_info):
    """discover_os_info() should detect Linux OS when uname succeeds."""
    from unittest.mock import MagicMock

    from nodescraper.connection.inband import CommandArtifact
    from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
    from nodescraper.enums import OSFamily
    from nodescraper.models.taskresult import TaskResult

    # Mock the connection to return Linux
    mock_conn = MagicMock()
    mock_conn.run_command.return_value = CommandArtifact(
        command="uname -s",
        stdout="Linux",
        stderr="",
        exit_code=0,
    )

    # Mock InBandConnectionManager instance
    mock_manager = MagicMock(spec=InBandConnectionManager)
    mock_manager.connection = mock_conn
    mock_manager.connect.return_value = TaskResult(status=ExecutionStatus.OK)
    mock_manager.disconnect.return_value = None

    # Create a mock class that returns our mock manager instance
    mock_class = Mock(return_value=mock_manager)
    mock_class.__name__ = "InBandConnectionManager"

    # Store original and patch
    import nodescraper.pluginexecutor

    original = nodescraper.pluginexecutor.InBandConnectionManager
    nodescraper.pluginexecutor.InBandConnectionManager = mock_class

    try:
        # Create executor
        executor = PluginExecutor(
            plugin_configs=[PluginConfig(plugins={})],
            system_info=system_info,
        )

        # Run OS discovery
        executor.discover_os_info()
    finally:
        # Restore original
        nodescraper.pluginexecutor.InBandConnectionManager = original

    # Verify Linux was detected
    assert system_info.os_family == OSFamily.LINUX
    mock_conn.run_command.assert_called_once_with("uname -s")


def test_discover_os_info_detects_arista_eos(system_info):
    """discover_os_info() should detect Arista EOS when uname fails but Arista command succeeds."""
    import json
    from unittest.mock import MagicMock

    from nodescraper.connection.inband import CommandArtifact
    from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
    from nodescraper.enums import OSFamily
    from nodescraper.models.taskresult import TaskResult

    arista_version = {
        "mfgName": "Arista Networks",
        "version": "4.32.1F",
        "modelName": "DCS-7280CR3-32P4",
    }

    # Mock the connection to fail uname but succeed with Arista command
    mock_conn = MagicMock()
    mock_conn.run_command.side_effect = [
        CommandArtifact(command="uname -s", stdout="", stderr="invalid", exit_code=1),
        CommandArtifact(
            command="show version | json | no-more",
            stdout=json.dumps(arista_version),
            stderr="",
            exit_code=0,
        ),
    ]

    # Mock InBandConnectionManager instance
    mock_manager = MagicMock(spec=InBandConnectionManager)
    mock_manager.connection = mock_conn
    mock_manager.connect.return_value = TaskResult(status=ExecutionStatus.OK)
    mock_manager.disconnect.return_value = None

    # Create a mock class that returns our mock manager instance
    mock_class = Mock(return_value=mock_manager)
    mock_class.__name__ = "InBandConnectionManager"

    # Store original and patch
    import nodescraper.pluginexecutor

    original = nodescraper.pluginexecutor.InBandConnectionManager
    nodescraper.pluginexecutor.InBandConnectionManager = mock_class

    try:
        # Create executor
        executor = PluginExecutor(
            plugin_configs=[PluginConfig(plugins={})],
            system_info=system_info,
        )

        # Run OS discovery
        executor.discover_os_info()
    finally:
        # Restore original
        nodescraper.pluginexecutor.InBandConnectionManager = original

    # Verify Arista EOS was detected
    assert system_info.os_family == OSFamily.EOS
    assert system_info.platform == "Arista EOS"
    assert system_info.metadata["os_version"] == "4.32.1F"
    assert system_info.metadata["device_model"] == "DCS-7280CR3-32P4"


def test_discover_os_info_skips_when_connection_fails(system_info, caplog):
    """discover_os_info() should skip detection and log when InBandConnectionManager fails to connect."""
    from unittest.mock import MagicMock

    from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
    from nodescraper.enums import OSFamily
    from nodescraper.models.taskresult import TaskResult

    # Mock InBandConnectionManager instance to fail connection
    mock_manager = MagicMock(spec=InBandConnectionManager)
    mock_manager.connect.return_value = TaskResult(
        status=ExecutionStatus.ERROR, message="Connection failed"
    )
    mock_manager.disconnect.return_value = None

    # Create a mock class that returns our mock manager instance
    mock_class = Mock(return_value=mock_manager)
    mock_class.__name__ = "InBandConnectionManager"

    # Store original and patch
    import nodescraper.pluginexecutor

    original = nodescraper.pluginexecutor.InBandConnectionManager
    nodescraper.pluginexecutor.InBandConnectionManager = mock_class

    try:
        # Create executor
        executor = PluginExecutor(
            plugin_configs=[PluginConfig(plugins={})],
            system_info=system_info,
        )

        # Run OS discovery
        with caplog.at_level(logging.INFO):
            executor.discover_os_info()
    finally:
        # Restore original
        nodescraper.pluginexecutor.InBandConnectionManager = original

    # Verify OS detection was skipped
    assert system_info.os_family == OSFamily.LINUX  # Default from fixture
    assert any("Skipping OS discovery" in record.message for record in caplog.records)


class RaisingPlugin(PluginInterface[MockConnectionManager, None]):
    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = MockConnectionManager

    def run(self, **kwargs):
        raise RuntimeError("plugin boom")


class FailingInitConnectionManager(MockConnectionManager):
    def __init__(self, *args, **kwargs):
        raise ValueError("bad connection args")


class FailingInitPlugin(PluginInterface[FailingInitConnectionManager, None]):
    __test__ = False  # Tells pytest to ignore this class

    CONNECTION_TYPE = FailingInitConnectionManager

    def run(self, **kwargs):
        return PluginResult(source="FailingInitPlugin", status=ExecutionStatus.OK)


class RaisingCollator(PluginResultCollator):
    def collate_results(self, plugin_results, connection_results, **kwargs):
        raise RuntimeError("collator boom")


def _isolated_registry(plugins: dict, managers: dict) -> PluginRegistry:
    registry = PluginRegistry(
        load_internal_plugins=False,
        load_entry_point_plugins=False,
        load_entry_point_connection_managers=False,
    )
    registry.plugins = plugins
    registry.connection_managers = managers
    return registry


def _read_events(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_connection_manager_instantiation_failure_is_logged_and_queue_continues(tmp_path, caplog):
    """A connection manager that cannot be built is logged and skipped, not fatal for the queue."""
    registry = _isolated_registry(
        {"FailingInitPlugin": FailingInitPlugin, "TestPluginB": TestPluginB},
        {
            "FailingInitConnectionManager": FailingInitConnectionManager,
            "MockConnectionManager": MockConnectionManager,
        },
    )
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={"FailingInitPlugin": {}, "TestPluginB": {}})],
        plugin_registry=registry,
        system_info=SystemInfo(os_family=OSFamily.LINUX),
        log_path=str(tmp_path),
    )

    with caplog.at_level(logging.ERROR):
        results = executor.run_queue()

    assert [r.source for r in results] == ["testB"]
    assert any(
        "FailingInitConnectionManager" in r.message and "bad connection args" in r.message
        for r in caplog.records
    )
    assert executor.connection_failure_results == []
    assert not (
        tmp_path / "connection" / resolve_log_dir_name("FailingInitConnectionManager")
    ).exists()


def test_connection_results_saved_and_closed_when_cleanup_step_raises(tmp_path):
    """Recorded connection failures are saved and connections closed even if a collator raises."""
    registry = _isolated_registry(
        {"RaisingPlugin": RaisingPlugin},
        {"MockConnectionManager": MockConnectionManager},
    )
    registry.result_collators = {"RaisingCollator": RaisingCollator}
    executor = PluginExecutor(
        plugin_configs=[
            PluginConfig(plugins={"RaisingPlugin": {}}, result_collators={"RaisingCollator": {}})
        ],
        plugin_registry=registry,
        system_info=SystemInfo(os_family=OSFamily.LINUX),
        log_path=str(tmp_path),
    )

    with patch.object(MockConnectionManager, "disconnect") as disconnect:
        with pytest.raises(RuntimeError, match="collator boom"):
            executor.run_queue()

    assert disconnect.call_count == 2
    conn_dir = tmp_path / "connection" / resolve_log_dir_name("MockConnectionManager")
    assert (conn_dir / "events.json").is_file()


def test_discover_os_info_result_saved_separately_from_connection_results(tmp_path):
    """The OS discovery connection result goes to os_discovery/, not to connection/."""
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={})],
        plugin_registry=_isolated_registry({}, {}),
        system_info=SystemInfo(location=SystemLocation.REMOTE),
        log_path=str(tmp_path),
    )

    executor.discover_os_info()

    events = _read_events(tmp_path / "os_discovery" / "events.json")
    assert events[0]["priority"] == "CRITICAL"
    assert events[0]["data"]["parent"] == "os_discovery"
    assert not (tmp_path / "connection").exists()


def test_discover_os_info_exception_saved_in_os_discovery_dir(tmp_path):
    """An exception while detecting the OS family is saved next to the discovery connection result."""
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={})],
        plugin_registry=_isolated_registry({}, {}),
        system_info=SystemInfo(),
        log_path=str(tmp_path),
    )

    with (
        patch.object(
            InBandConnectionManager, "connect", return_value=TaskResult(status=ExecutionStatus.OK)
        ),
        patch(
            "nodescraper.pluginexecutor.discover_and_write_os_family",
            side_effect=RuntimeError("detect boom"),
        ),
    ):
        executor.discover_os_info()

    events = _read_events(tmp_path / "os_discovery" / "events.json")
    assert "detect boom" in events[0]["description"]
    assert events[0]["priority"] == "ERROR"
    assert events[0]["data"]["parent"] == "os_discovery"
    assert not (tmp_path / "connection").exists()


# ---------------------------------------------------------------------------
# Connection cleanup when exceptions are raised at different points of a run
# ---------------------------------------------------------------------------


class TrackedManager(MockConnectionManager):
    """Starts disconnected, connects on demand and records every disconnect."""

    calls: list = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection = None
        self.result = self._init_result()

    def connect(self):
        TrackedManager.calls.append(("connect", type(self).__name__))
        self.connection = MagicMock()
        self.result.status = ExecutionStatus.OK
        return self.result

    def disconnect(self):
        TrackedManager.calls.append(("disconnect", type(self).__name__))
        self.connection = None


class ManagerA(TrackedManager):
    pass


class ManagerB(TrackedManager):
    pass


class AbstractManager(TrackedManager):
    @abc.abstractmethod
    def extra(self): ...


def _make_plugin(manager_cls, name, outcome="ok"):
    """Plugin that connects, then returns OK / ERROR or raises."""

    class _Plugin(PluginInterface[manager_cls, None]):
        CONNECTION_TYPE = manager_cls

        def run(self, **kwargs):
            TrackedManager.calls.append(("run", name))
            self.connection_manager.connect()
            if outcome == "raise":
                raise RuntimeError(f"{name} boom")
            status = ExecutionStatus.ERROR if outcome == "error" else ExecutionStatus.OK
            return PluginResult(source=name, status=status)

    _Plugin.__name__ = name
    return _Plugin


class InitFailsPlugin(PluginInterface[TrackedManager, None]):
    __test__ = False

    CONNECTION_TYPE = TrackedManager

    def __init__(self, *args, **kwargs):
        raise RuntimeError("init boom")

    def run(self, **kwargs):
        return PluginResult(source="init_fails", status=ExecutionStatus.OK)


@pytest.fixture
def tracked():
    TrackedManager.calls = []
    yield TrackedManager.calls
    TrackedManager.calls = []


def _executor(tmp_path, plugins, managers, config_plugins, **kwargs):
    config_kwargs = kwargs.pop("config_kwargs", {})
    registry = _isolated_registry(plugins, managers)
    registry.result_collators = kwargs.pop("collators", {})
    return PluginExecutor(
        plugin_configs=[PluginConfig(plugins=config_plugins, **config_kwargs)],
        plugin_registry=registry,
        system_info=kwargs.pop("system_info", SystemInfo(os_family=OSFamily.LINUX)),
        log_path=str(tmp_path),
        **kwargs,
    )


def _conn_dir(tmp_path, manager_cls):
    return tmp_path / "connection" / resolve_log_dir_name(manager_cls.__name__)


def _disconnects(calls, name="TrackedManager"):
    return [c for c in calls if c == ("disconnect", name)]


def _failing_and_ok_plugins():
    return (
        {"Failing": InitFailsPlugin, "Ok": _make_plugin(TrackedManager, "Ok")},
        {"TrackedManager": TrackedManager},
        {"Failing": {}, "Ok": {}},
    )


@pytest.mark.parametrize(
    "spot, expected_exception",
    [
        ("plugin_init", "RuntimeError"),
        ("global_args", "TypeError"),
        ("plugin_run", "RuntimeError"),
        ("result_hook", "RuntimeError"),
    ],
)
def test_exception_at_each_plugin_spot_closes_connection_and_saves_result(
    tmp_path, tracked, spot, expected_exception
):
    """Whichever step of running a plugin raises, its connection is closed right away,
    the failure is saved in the connection folder and the next plugin still runs."""
    plugins, managers, config = _failing_and_ok_plugins()
    if spot != "plugin_init":
        plugins["Failing"] = _make_plugin(
            TrackedManager, "Failing", "raise" if spot == "plugin_run" else "ok"
        )

    def hook(result):
        if result.source == "Failing":
            raise RuntimeError("hook boom")

    executor = _executor(
        tmp_path,
        plugins,
        managers,
        config,
        plugin_run_result_hooks=[hook] if spot == "result_hook" else None,
    )

    if spot == "global_args":
        real = PluginExecutor.apply_global_args_to_plugin

        def flaky(self, plugin_inst, plugin_class, global_args):
            if plugin_class.__name__ == "Failing":
                raise TypeError("bad global args")
            return real(self, plugin_inst, plugin_class, global_args)

        with patch.object(PluginExecutor, "apply_global_args_to_plugin", flaky):
            results = executor.run_queue()
    else:
        results = executor.run_queue()

    assert "Ok" in [r.source for r in results]
    # closed straight after the failure (before the next plugin ran) and again during cleanup
    assert len(_disconnects(tracked)) == 2
    assert tracked.index(("disconnect", "TrackedManager")) < tracked.index(("run", "Ok"))

    conn_dir = _conn_dir(tmp_path, TrackedManager)
    events = _read_events(conn_dir / "events.json")
    assert len(events) == 1
    assert "Failing" in events[0]["description"]
    assert events[0]["priority"] == "CRITICAL"
    assert events[0]["data"]["exception_type"] == expected_exception
    # the manager's own OK result must not overwrite the recorded failure
    with open(conn_dir / "result.json", encoding="utf-8") as f:
        assert json.load(f)["status"] == "EXECUTION_FAILURE"


def test_invalid_global_args_skips_plugin_without_connection_failure(tmp_path, tracked):
    """A ValueError from global args skips the plugin: no connection failure, closed at cleanup."""
    executor = _executor(
        tmp_path,
        {"Ok": _make_plugin(TrackedManager, "Ok")},
        {"TrackedManager": TrackedManager},
        {"Ok": {}},
    )

    with patch.object(
        PluginExecutor, "apply_global_args_to_plugin", side_effect=ValueError("bad value")
    ):
        results = executor.run_queue()

    assert results == []
    assert executor.connection_failure_results == []
    assert _disconnects(tracked) == [("disconnect", "TrackedManager")]
    assert not (tmp_path / "connection").exists()


def test_unresolvable_connection_manager_is_logged_and_queue_continues(tmp_path, tracked, caplog):
    """An abstract / unregistered CONNECTION_TYPE is logged as an error and the plugin skipped."""
    abstract_plugin = _make_plugin(AbstractManager, "Abstract")
    executor = _executor(
        tmp_path,
        {"Abstract": abstract_plugin, "Ok": _make_plugin(TrackedManager, "Ok")},
        {"TrackedManager": TrackedManager},
        {"Abstract": {}, "Ok": {}},
    )

    with caplog.at_level(logging.ERROR):
        results = executor.run_queue()

    assert [r.source for r in results] == ["Ok"]
    assert any("AbstractManager" in r.message and "Abstract" in r.message for r in caplog.records)
    assert executor.connection_failure_results == []
    assert not _conn_dir(tmp_path, AbstractManager).exists()


def test_oob_plugin_without_redfish_config_is_logged_and_queue_continues(tmp_path, tracked, caplog):
    """An OOB plugin without a RedfishConnectionManager config logs an error and is skipped."""

    class NoConfigOobPlugin(OOBSSHDataPlugin):
        DATA_MODEL = DummyDataModel

    executor = _executor(
        tmp_path,
        {"NoConfigOobPlugin": NoConfigOobPlugin, "Ok": _make_plugin(TrackedManager, "Ok")},
        {"TrackedManager": TrackedManager},
        {"NoConfigOobPlugin": {}, "Ok": {}},
    )

    with caplog.at_level(logging.ERROR):
        results = executor.run_queue()

    assert [r.source for r in results] == ["Ok"]
    assert any("RedfishConnectionManager" in r.message for r in caplog.records)
    assert executor.connection_failure_results == []
    assert not _conn_dir(tmp_path, OobSshConnectionManager).exists()


def test_post_action_plugin_exception_closes_connection_and_saves_result(tmp_path, tracked):
    """A post-action plugin raising is handled like a primary plugin failure."""
    executor = _executor(
        tmp_path,
        {
            "Primary": _make_plugin(TrackedManager, "Primary", "error"),
            "PostAction": _make_plugin(TrackedManager, "PostAction", "raise"),
        },
        {"TrackedManager": TrackedManager},
        {"Primary": {}},
        config_kwargs={
            "post_action_plugins": [
                PostActionPluginConfig(
                    plugin="PostAction", conditions=[PostActionCondition(status="ERROR")]
                )
            ]
        },
    )

    results = executor.run_queue()

    assert [r.source for r in results] == ["Primary"]
    assert len(_disconnects(tracked)) == 2
    events = _read_events(_conn_dir(tmp_path, TrackedManager) / "events.json")
    assert "PostAction" in events[0]["description"]


def test_queue_level_exception_still_saves_and_closes_connections(tmp_path, tracked):
    """An exception escaping _run_single_plugin aborts the queue but connections are cleaned up."""
    plugins = {
        "First": _make_plugin(TrackedManager, "First"),
        "Second": _make_plugin(TrackedManager, "Second"),
    }
    executor = _executor(
        tmp_path, plugins, {"TrackedManager": TrackedManager}, {"First": {}, "Second": {}}
    )
    real = PluginExecutor._run_single_plugin

    def flaky(self, plugin_name, *args, **kwargs):
        if plugin_name == "Second":
            raise RuntimeError("queue boom")
        return real(self, plugin_name, *args, **kwargs)

    with patch.object(PluginExecutor, "_run_single_plugin", flaky):
        results = executor.run_queue()

    assert [r.source for r in results] == ["First"]
    assert ("run", "Second") not in tracked
    assert _disconnects(tracked) == [("disconnect", "TrackedManager")]
    with open(_conn_dir(tmp_path, TrackedManager) / "result.json", encoding="utf-8") as f:
        assert json.load(f)["status"] == "OK"


def test_post_action_evaluation_exception_still_closes_connections(tmp_path, tracked):
    """If post-action handling itself raises, connections are still saved and closed."""
    executor = _executor(
        tmp_path,
        {"First": _make_plugin(TrackedManager, "First")},
        {"TrackedManager": TrackedManager},
        {"First": {}},
    )

    with patch.object(PluginExecutor, "_run_post_actions", side_effect=RuntimeError("post boom")):
        with pytest.raises(RuntimeError, match="post boom"):
            executor.run_queue()

    assert _disconnects(tracked) == [("disconnect", "TrackedManager")]
    assert (_conn_dir(tmp_path, TrackedManager) / "result.json").is_file()


def test_cleanup_failure_for_one_connection_does_not_block_the_others(tmp_path, tracked):
    """A manager whose disconnect raises must not stop the other managers being closed."""
    executor = _executor(
        tmp_path,
        {
            "PluginA": _make_plugin(ManagerA, "PluginA"),
            "PluginB": _make_plugin(ManagerB, "PluginB"),
        },
        {"ManagerA": ManagerA, "ManagerB": ManagerB},
        {"PluginA": {}, "PluginB": {}},
    )

    with patch.object(ManagerA, "disconnect", side_effect=OSError("cleanup boom")):
        results = executor.run_queue()

    assert {r.source for r in results} == {"PluginA", "PluginB"}
    assert _disconnects(tracked, "ManagerB") == [("disconnect", "ManagerB")]
    with open(_conn_dir(tmp_path, ManagerB) / "result.json", encoding="utf-8") as f:
        assert json.load(f)["status"] == "OK"


def test_failing_connection_hook_does_not_stop_cleanup(tmp_path, tracked):
    """A hook that raises while saving a recorded failure must not abort cleanup."""

    class RaisingOnFailureHook(TaskResultHook):
        def process_result(self, task_result, data=None, **kwargs):
            if task_result.status == ExecutionStatus.EXECUTION_FAILURE:
                raise OSError("disk full")

    executor = _executor(
        tmp_path,
        {
            "Failing": _make_plugin(ManagerA, "Failing", "raise"),
            "Ok": _make_plugin(ManagerB, "Ok"),
        },
        {"ManagerA": ManagerA, "ManagerB": ManagerB},
        {"Failing": {}, "Ok": {}},
    )
    executor.connection_result_hooks.append(RaisingOnFailureHook())

    results = executor.run_queue()

    assert [r.source for r in results] == ["Ok"]
    assert len(_disconnects(tracked, "ManagerA")) == 2
    assert len(_disconnects(tracked, "ManagerB")) == 1


def test_failure_close_error_does_not_mask_plugin_failure(tmp_path, tracked):
    """If disconnect raises while closing after a plugin failure, the failure is still recorded."""
    executor = _executor(
        tmp_path,
        {"Failing": _make_plugin(ManagerA, "Failing", "raise"), "Ok": _make_plugin(ManagerB, "Ok")},
        {"ManagerA": ManagerA, "ManagerB": ManagerB},
        {"Failing": {}, "Ok": {}},
    )

    with patch.object(ManagerA, "disconnect", side_effect=OSError("close boom")):
        results = executor.run_queue()

    assert [r.source for r in results] == ["Ok"]
    events = _read_events(_conn_dir(tmp_path, ManagerA) / "events.json")
    assert events[0]["data"]["exception_type"] == "RuntimeError"
    assert "Failing" in events[0]["description"]


# ---------------------------------------------------------------------------
# OS discovery
# ---------------------------------------------------------------------------


def _discovery_executor(tmp_path, **system_kwargs):
    return PluginExecutor(
        plugin_configs=[PluginConfig(plugins={})],
        plugin_registry=_isolated_registry({}, {}),
        system_info=SystemInfo(**system_kwargs),
        log_path=str(tmp_path),
    )


def test_discover_os_info_success_saves_result_in_os_discovery_dir(tmp_path):
    executor = _discovery_executor(tmp_path)

    with (
        patch("nodescraper.pluginexecutor.discover_and_write_os_family") as detect,
        patch.object(InBandConnectionManager, "disconnect", autospec=True) as disconnect,
    ):
        executor.discover_os_info()

    detect.assert_called_once()
    disconnect.assert_called_once()
    with open(tmp_path / "os_discovery" / "result.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["status"] == "OK"
    assert saved["parent"] == "os_discovery"
    assert not (tmp_path / "os_discovery" / "events.json").exists()
    assert not (tmp_path / "connection").exists()


@pytest.mark.parametrize(
    "spot, expected_priority, events_file",
    [
        ("connect_raises", "CRITICAL", "events.json"),
        ("no_credentials", "CRITICAL", "events.json"),
        # the successful connect result is already result.json, so the failure is logged as (1)
        ("detection_raises", "ERROR", "events(1).json"),
    ],
)
def test_discover_os_info_failures_are_saved_in_os_discovery_dir_and_closed(
    tmp_path, spot, expected_priority, events_file
):
    system_kwargs = {"location": SystemLocation.REMOTE} if spot == "no_credentials" else {}
    executor = _discovery_executor(tmp_path, **system_kwargs)
    original_family = executor.system_info.os_family

    patches = [patch.object(InBandConnectionManager, "disconnect", autospec=True)]
    if spot == "connect_raises":
        patches.append(
            patch(
                "nodescraper.connection.inband.inbandmanager.LocalShell",
                side_effect=OSError("no shell"),
            )
        )
    elif spot == "detection_raises":
        patches.append(
            patch(
                "nodescraper.pluginexecutor.discover_and_write_os_family",
                side_effect=RuntimeError("detect boom"),
            )
        )
    with patches[0] as disconnect:
        for extra in patches[1:]:
            extra.start()
        try:
            executor.discover_os_info()
        finally:
            for extra in patches[1:]:
                extra.stop()

    disconnect.assert_called_once()
    assert executor.system_info.os_family == original_family
    events = _read_events(tmp_path / "os_discovery" / events_file)
    assert events[-1]["priority"] == expected_priority
    assert events[-1]["data"]["parent"] == "os_discovery"
    assert not (tmp_path / "connection").exists()


def test_discover_os_info_disconnect_error_does_not_propagate(tmp_path):
    executor = _discovery_executor(tmp_path)

    with (
        patch("nodescraper.pluginexecutor.discover_and_write_os_family"),
        patch.object(InBandConnectionManager, "disconnect", side_effect=OSError("close boom")),
    ):
        executor.discover_os_info()


def test_discover_os_info_constructor_failure_does_not_raise(tmp_path):
    executor = _discovery_executor(tmp_path)

    with patch(
        "nodescraper.pluginexecutor.InBandConnectionManager",
        side_effect=ValueError("bad connection args"),
    ):
        executor.discover_os_info()

    assert not (tmp_path / "connection").exists()


def test_discovery_and_plugin_results_go_to_separate_folders(tmp_path, tracked):
    """OS discovery output and plugin connection output never share a folder."""
    executor = _executor(
        tmp_path,
        {"Failing": _make_plugin(TrackedManager, "Failing", "raise")},
        {"TrackedManager": TrackedManager},
        {"Failing": {}},
        system_info=SystemInfo(os_family=OSFamily.UNKNOWN),
    )

    with patch("nodescraper.pluginexecutor.discover_and_write_os_family"):
        executor.run_queue()

    discovery = json.loads((tmp_path / "os_discovery" / "result.json").read_text())
    assert discovery["task"] == "InBandConnectionManager"
    assert discovery["status"] == "OK"
    assert not (tmp_path / "os_discovery" / "events.json").exists()

    plugin_events = _read_events(_conn_dir(tmp_path, TrackedManager) / "events.json")
    assert "Failing" in plugin_events[0]["description"]
    assert [p.name for p in (tmp_path / "connection").iterdir()] == [
        resolve_log_dir_name("TrackedManager")
    ]


def test_run_queue_continues_when_discovery_connection_cannot_be_built(tmp_path, tracked):
    executor = _executor(
        tmp_path,
        {"Ok": _make_plugin(TrackedManager, "Ok")},
        {"TrackedManager": TrackedManager},
        {"Ok": {}},
        system_info=SystemInfo(os_family=OSFamily.UNKNOWN),
    )

    with patch(
        "nodescraper.pluginexecutor.InBandConnectionManager", side_effect=ValueError("bad args")
    ):
        results = executor.run_queue()

    assert [r.source for r in results] == ["Ok"]


class _OkCollector(DataCollector):
    DATA_MODEL = DummyDataModel

    def collect_data(self, args=None):
        return TaskResult(status=ExecutionStatus.OK), DummyDataModel()


def _make_data_plugin(name):
    class _DataPlugin(DataPlugin):
        DATA_MODEL = DummyDataModel
        CONNECTION_TYPE = TrackedManager
        COLLECTOR = _OkCollector

    _DataPlugin.__name__ = name
    return _DataPlugin


def test_data_plugins_share_one_connection_by_default(tmp_path, tracked):
    """No argument is needed for plugins to share the executor's connection."""
    executor = _executor(
        tmp_path,
        {"First": _make_data_plugin("First"), "Second": _make_data_plugin("Second")},
        {"TrackedManager": TrackedManager},
        {"First": {"analysis": False}, "Second": {"analysis": False}},
    )

    results = executor.run_queue()

    assert [r.status for r in results] == [ExecutionStatus.OK, ExecutionStatus.OK]
    assert tracked == [("connect", "TrackedManager"), ("disconnect", "TrackedManager")]


def test_plugin_config_preserve_connection_false_is_honored(tmp_path, tracked):
    """A plugin configured with preserve_connection=False closes the shared connection and the
    next plugin reconnects; the executor no longer overrides the value."""
    executor = _executor(
        tmp_path,
        {"First": _make_data_plugin("First"), "Second": _make_data_plugin("Second")},
        {"TrackedManager": TrackedManager},
        {
            "First": {"analysis": False, "preserve_connection": False},
            "Second": {"analysis": False},
        },
    )

    results = executor.run_queue()

    assert [r.status for r in results] == [ExecutionStatus.OK, ExecutionStatus.OK]
    assert tracked == [
        ("connect", "TrackedManager"),
        ("disconnect", "TrackedManager"),  # First closed it
        ("connect", "TrackedManager"),  # Second reconnected
        ("disconnect", "TrackedManager"),  # executor cleanup
    ]
    with open(_conn_dir(tmp_path, TrackedManager) / "result.json", encoding="utf-8") as f:
        assert json.load(f)["status"] == "OK"


def test_global_args_preserve_connection_false_is_honored(tmp_path, tracked):
    executor = _executor(
        tmp_path,
        {"First": _make_data_plugin("First"), "Second": _make_data_plugin("Second")},
        {"TrackedManager": TrackedManager},
        {"First": {"analysis": False}, "Second": {"analysis": False}},
        config_kwargs={"global_args": {"preserve_connection": False}},
    )

    executor.run_queue()

    # each plugin closes it after collecting, then the executor's cleanup closes it once more
    assert len(_disconnects(tracked)) == 3
    assert len([c for c in tracked if c[0] == "connect"]) == 2


class _ConnArgs(BaseModel):
    hostname: str
    port: int = 22


class _ModelledManager(MockConnectionManager):
    CONNECTION_ARGS_MODEL = _ConnArgs


class _ModelledPlugin(PluginInterface[_ModelledManager, None]):
    __test__ = False

    CONNECTION_TYPE = _ModelledManager

    def run(self, connection_args=None, **kwargs):
        return PluginResult(source="modelled", status=ExecutionStatus.OK)


class _NoConnectionPlugin(PluginInterface[MockConnectionManager, None]):
    __test__ = False

    CONNECTION_TYPE = None

    def run(self, connection_args=None):
        return PluginResult(source="none", status=ExecutionStatus.OK)


def _apply_connection_config(plugin_class, connection_config):
    return PluginExecutor(plugin_configs=[]).apply_global_args_to_plugin(
        plugin_class(), plugin_class, {}, connection_config
    )


def test_global_connection_config_gives_plugin_its_connection_args_without_unknown_keys():
    config = {
        "_ModelledManager": {"hostname": "h", "port": 2, "other": "x"},
        "SomeOtherManager": {"hostname": "other"},
    }

    run_args = _apply_connection_config(_ModelledPlugin, config)

    assert run_args["connection_args"] == {"hostname": "h", "port": 2}


def test_global_connection_config_adds_nothing_without_entry_type_or_config():
    for plugin_class, config in (
        (_ModelledPlugin, {"Other": {}}),
        (_ModelledPlugin, {}),
        (_ModelledPlugin, None),
        (_NoConnectionPlugin, {"MockConnectionManager": {"x": 1}}),
    ):
        assert "connection_args" not in _apply_connection_config(plugin_class, config)


def test_global_connection_config_model_instance_is_passed_unchanged():
    model = _ConnArgs(hostname="h")

    run_args = _apply_connection_config(_ModelledPlugin, {"_ModelledManager": model})

    assert run_args["connection_args"] is model


def test_global_connection_config_without_args_model_is_an_unfiltered_copy():
    class Plain(PluginInterface[MockConnectionManager, None]):
        CONNECTION_TYPE = MockConnectionManager

        def run(self, connection_args=None):
            return PluginResult(source="plain", status=ExecutionStatus.OK)

    config = {"MockConnectionManager": {"anything": 1}}

    args = _apply_connection_config(Plain, config)["connection_args"]

    assert args == {"anything": 1}
    assert args is not config["MockConnectionManager"]


def test_global_connection_config_is_not_added_when_run_does_not_accept_it():
    # TestPluginB.run(self, test_arg=None) has no connection_args parameter
    run_args = _apply_connection_config(TestPluginB, {"MockConnectionManager": {"x": 1}})

    assert "connection_args" not in run_args


def test_global_connection_config_result_builds_the_real_ssh_model():
    from nodescraper.connection.inband import InBandConnectionManager as InBand
    from nodescraper.connection.inband.sshparams import SSHConnectionParams

    class InBandPlugin(PluginInterface[InBand, None]):
        CONNECTION_TYPE = InBand

        def run(self, connection_args=None):
            return PluginResult(source="inband", status=ExecutionStatus.OK)

    config = {
        "InBandConnectionManager": {"hostname": "h", "username": "u", "key_filename": "k", "x": 1}
    }

    args = _apply_connection_config(InBandPlugin, config)["connection_args"]

    assert SSHConnectionParams(**args).username == "u"
    assert "x" not in args
