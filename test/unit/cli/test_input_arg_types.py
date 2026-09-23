# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from nodescraper.cli.inputargtypes import ModelArgHandler


class SampleArgs(BaseModel):
    name: str = ""
    count: int = 0


def _write(tmp_path: Path, payload) -> str:
    arg_file = tmp_path / "arg.json"
    arg_file.write_text(json.dumps(payload), encoding="utf-8")
    return str(arg_file)


def test_process_file_arg_builds_model(tmp_path: Path):
    """Baseline: a valid json object is loaded into the model."""
    path = _write(tmp_path, {"name": "abc", "count": 2})

    assert ModelArgHandler(SampleArgs).process_file_arg(path) == SampleArgs(name="abc", count=2)


def test_process_file_arg_invalid_value_raises_arg_type_error(tmp_path: Path):
    """Baseline: a validation failure is surfaced as an argparse error."""
    path = _write(tmp_path, {"count": "not-an-int"})

    with pytest.raises(argparse.ArgumentTypeError):
        ModelArgHandler(SampleArgs).process_file_arg(path)


def test_process_file_arg_non_object_json_raises_arg_type_error(tmp_path: Path):
    """A json file that is not an object must be reported as an argparse error."""
    path = _write(tmp_path, [{"name": "abc"}])

    with pytest.raises(argparse.ArgumentTypeError):
        ModelArgHandler(SampleArgs).process_file_arg(path)
