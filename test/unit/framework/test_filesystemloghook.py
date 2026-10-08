# Copyright (C) 2025 Advanced Micro Devices, Inc.

import json
import os
import shutil
import tempfile
from typing import Iterator

import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.models import DataModel, FileModel, TaskResult
from nodescraper.taskresulthooks.filesystemloghook import FileSystemLogHook


class SampleModel(DataModel):
    name: str
    value: int


class SampleModelWithFileModel(DataModel):
    name: str
    log_file: FileModel
    extra_files: list[FileModel] = []


@pytest.fixture
def log_dir() -> Iterator[str]:
    """Temporary log directory that is always removed after the test."""
    path = tempfile.mkdtemp(prefix="filesystemloghook_")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_result() -> TaskResult:
    return TaskResult(
        status=ExecutionStatus.OK,
        message="done",
        task="SampleCollector",
        parent="SamplePlugin",
    )


def test_process_result_without_data(log_dir):
    hook = FileSystemLogHook(log_base_path=log_dir)

    hook.process_result(make_result())

    task_dir = os.path.join(log_dir, "sample_plugin", "sample_collector")
    assert os.listdir(task_dir) == ["result.json"]
    with open(os.path.join(task_dir, "result.json"), encoding="utf-8") as f:
        assert json.load(f)["message"] == "done"


def test_process_result_logs_sample_model(log_dir):
    hook = FileSystemLogHook(log_base_path=log_dir)
    data = SampleModel(name="sample", value=7)

    hook.process_result(make_result(), data)

    task_dir = os.path.join(log_dir, "sample_plugin", "sample_collector")
    assert sorted(os.listdir(task_dir)) == ["result.json", "samplemodel.json"]
    with open(os.path.join(task_dir, "samplemodel.json"), encoding="utf-8") as f:
        assert json.load(f) == {"name": "sample", "value": 7}


def test_process_result_logs_sample_model_with_file_model(log_dir):
    hook = FileSystemLogHook(log_base_path=log_dir)
    data = SampleModelWithFileModel(
        name="with-files",
        log_file=FileModel(file_name="main.log", file_contents=b"main contents"),
        extra_files=[
            FileModel(file_name="extra1.log", file_contents="extra one"),
            FileModel(file_name="extra2.bin", file_contents=b"\x00\x01\x02"),
        ],
    )

    hook.process_result(make_result(), data)

    task_dir = os.path.join(log_dir, "sample_plugin", "sample_collector")
    assert sorted(os.listdir(task_dir)) == [
        "extra1.log",
        "extra2.bin",
        "main.log",
        "result.json",
        "samplemodelwithfilemodel.json",
    ]
    with open(os.path.join(task_dir, "main.log"), "rb") as f:
        assert f.read() == b"main contents"
    with open(os.path.join(task_dir, "extra1.log"), "rb") as f:
        assert f.read() == b"extra one"
    with open(os.path.join(task_dir, "extra2.bin"), "rb") as f:
        assert f.read() == b"\x00\x01\x02"

    # file_contents is excluded from the model json
    with open(os.path.join(task_dir, "samplemodelwithfilemodel.json"), encoding="utf-8") as f:
        model_json = json.load(f)
    assert model_json["name"] == "with-files"
    assert model_json["log_file"] == {"file_name": "main.log"}


def test_process_result_without_task_path(log_dir):
    hook = FileSystemLogHook(log_base_path=log_dir, include_task_path=False)

    hook.process_result(make_result(), SampleModel(name="flat", value=1))

    assert sorted(os.listdir(log_dir)) == ["result.json", "samplemodel.json"]


def test_process_result_rejects_malicious_file_model(log_dir):
    base = os.path.join(log_dir, "logs")
    hook = FileSystemLogHook(log_base_path=base)
    data = SampleModelWithFileModel(
        name="evil",
        log_file=FileModel(file_name="main.log", file_contents=b"fine"),
        extra_files=[FileModel(file_name="../../escaped.log", file_contents=b"nope")],
    )

    with pytest.raises(ValueError, match="outside of"):
        hook.process_result(make_result(), data)

    assert not os.path.exists(os.path.join(log_dir, "escaped.log"))
    assert not os.path.exists(os.path.join(os.path.dirname(log_dir), "escaped.log"))
    task_dir = os.path.join(base, "sample_plugin", "sample_collector")
    assert "samplemodelwithfilemodel.json" not in os.listdir(task_dir)
