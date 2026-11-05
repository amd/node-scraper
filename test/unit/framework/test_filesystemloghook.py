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
import json

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import DataModel, Event, TaskResult
from nodescraper.taskresulthooks import FileSystemLogHook


class _Model(DataModel):
    value: str = "x"


def _result(task="MyTask", parent="MyParent", message="", events=()):
    return TaskResult(
        task=task,
        parent=parent,
        status=ExecutionStatus.OK,
        message=message,
        events=[
            Event(
                reporter="test",
                category=EventCategory.RUNTIME,
                description=d,
                priority=EventPriority.WARNING,
            )
            for d in events
        ],
    )


def _names(path):
    return sorted(p.name for p in path.iterdir())


def _read(path):
    return json.loads(path.read_text())


def test_first_result_uses_plain_file_names(tmp_path):
    hook = FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False)

    hook.process_result(_result(events=["one"]))

    assert _names(tmp_path) == ["events.json", "result.json"]


def test_later_results_in_same_directory_get_an_integer_and_keep_earlier_logs(tmp_path):
    hook = FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False)

    hook.process_result(_result(message="first", events=["one"]))
    hook.process_result(_result(message="second", events=["two"]))
    hook.process_result(_result(message="third", events=["three"]))

    assert _names(tmp_path) == [
        "events(1).json",
        "events(2).json",
        "events.json",
        "result(1).json",
        "result(2).json",
        "result.json",
    ]
    assert _read(tmp_path / "result.json")["message"] == "first"
    assert _read(tmp_path / "result(1).json")["message"] == "second"
    assert _read(tmp_path / "result(2).json")["message"] == "third"
    # events are not merged across results: each result keeps its own events file
    assert [e["description"] for e in _read(tmp_path / "events.json")] == ["one"]
    assert [e["description"] for e in _read(tmp_path / "events(1).json")] == ["two"]
    assert [e["description"] for e in _read(tmp_path / "events(2).json")] == ["three"]


def test_result_and_events_share_the_same_index_when_earlier_result_had_no_events(tmp_path):
    hook = FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False)

    hook.process_result(_result(message="first"))
    hook.process_result(_result(message="second", events=["only"]))

    assert _names(tmp_path) == ["events(1).json", "result(1).json", "result.json"]


def test_results_for_different_tasks_do_not_get_an_integer(tmp_path):
    hook = FileSystemLogHook(log_base_path=str(tmp_path))

    hook.process_result(_result(task="TaskA"))
    hook.process_result(_result(task="TaskB"))

    assert (tmp_path / "my_parent" / "task_a" / "result.json").is_file()
    assert (tmp_path / "my_parent" / "task_b" / "result.json").is_file()
    assert not list(tmp_path.rglob("result(1).json"))


def test_a_new_hook_instance_does_not_overwrite_logs_already_on_disk(tmp_path):
    FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False).process_result(
        _result(message="old")
    )

    FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False).process_result(
        _result(message="new")
    )

    assert _read(tmp_path / "result.json")["message"] == "old"
    assert _read(tmp_path / "result(1).json")["message"] == "new"


def test_data_model_is_logged_next_to_each_result_without_overwriting(tmp_path):
    hook = FileSystemLogHook(log_base_path=str(tmp_path), include_task_path=False)

    hook.process_result(_result(), data=_Model(value="a"))
    hook.process_result(_result(), data=_Model(value="b"))

    assert _read(tmp_path / "_model.json")["value"] == "a"
    assert _read(tmp_path / "_model(1).json")["value"] == "b"
