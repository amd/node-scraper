# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces.plugin import PluginInterface
from nodescraper.interfaces.taskresulthook import TaskResultHook
from nodescraper.models import PluginResult, TaskResult
from nodescraper.taskresulthooks.filesystemloghook import FileSystemLogHook


class DummyHook(TaskResultHook):
    def process_result(self, task_result: TaskResult, **kwargs):
        return None


class DummyPlugin(PluginInterface):
    def run(self, **kwargs) -> PluginResult:
        return PluginResult(source=self.__class__.__name__, status=ExecutionStatus.OK)


def test_log_path_adds_filesystem_hook():
    """Baseline: a plugin given a log path gets a filesystem hook for that path."""
    plugin = DummyPlugin(log_path="/tmp/run-a")

    hooks = [h for h in plugin.task_result_hooks if isinstance(h, FileSystemLogHook)]
    assert [h.log_base_path for h in hooks] == ["/tmp/run-a"]


def test_shared_hook_list_does_not_leak_log_path_between_plugins():
    """A hook list shared by two plugins must not give the second plugin the first's log path."""
    shared_hooks: list = [DummyHook()]

    DummyPlugin(log_path="/tmp/run-a", task_result_hooks=shared_hooks)
    plugin_b = DummyPlugin(log_path="/tmp/run-b", task_result_hooks=shared_hooks)

    hooks = [h for h in plugin_b.task_result_hooks if isinstance(h, FileSystemLogHook)]
    assert "/tmp/run-b" in [h.log_base_path for h in hooks]
