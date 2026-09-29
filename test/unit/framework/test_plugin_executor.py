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
import logging
from typing import Optional

import pytest
from framework.common.shared_utils import DummyDataModel, MockConnectionManager
from pydantic import BaseModel

from nodescraper.enums import ExecutionStatus
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces import PluginInterface
from nodescraper.models import PluginConfig, PluginResult
from nodescraper.models.postactioncondition import PostActionCondition
from nodescraper.models.postactionpluginconfig import PostActionPluginConfig
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry


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
    preserve_connection = False
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
        "preserve_connection": True,
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
    assert run_payload["preserve_connection"] is True
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
    from unittest.mock import MagicMock, Mock

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
    from unittest.mock import MagicMock, Mock

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
    from unittest.mock import MagicMock, Mock

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
