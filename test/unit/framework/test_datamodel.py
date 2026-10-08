# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from nodescraper.models.datamodel import DataModel, FileModel


class FolderDataModel(DataModel):
    value: str = ""

    @classmethod
    def build_from_folder(cls, folder_path: str) -> "FolderDataModel":
        return cls(value=os.path.basename(folder_path))


class CperListDataModel(DataModel):
    value: str = "ok"
    cper_data: list[FileModel] = []


def test_import_model_from_dict():
    """Baseline: a dict is passed straight to the model constructor."""
    assert FolderDataModel.import_model({"value": "abc"}).value == "abc"


def test_import_model_from_json_file(tmp_path: Path):
    """Baseline: a json file path is read and parsed."""
    model_file = tmp_path / "model.json"
    model_file.write_text(json.dumps({"value": "from-file"}), encoding="utf-8")

    assert FolderDataModel.import_model(str(model_file)).value == "from-file"


def test_import_model_from_directory_uses_build_from_folder(tmp_path: Path):
    """A directory path must be dispatched to build_from_folder."""
    folder = tmp_path / "collected"
    folder.mkdir()

    assert FolderDataModel.import_model(str(folder)).value == "collected"


def test_filemodel_json_roundtrips_binary_cper_bytes():
    """Non-UTF-8 CPER bytes serialize as base64 and reload intact as bytes."""
    cper_bytes = b"CPER\x00\x01\xff\xff\xff\xff"
    model = FileModel(file_contents=cper_bytes, file_name="corrected-1.cper")
    dumped = model.model_dump_json()
    payload = json.loads(dumped)
    assert payload["file_contents"] == base64.urlsafe_b64encode(cper_bytes).decode("ascii")

    reloaded = FileModel.model_validate_json(dumped)
    assert isinstance(reloaded.file_contents, bytes)
    assert reloaded.file_contents == cper_bytes


def test_filemodel_python_strings_are_utf8_not_base64():
    """A plain string that is also valid base64 must be stored as UTF-8 text."""
    text = "VGVzdA=="
    model = FileModel(file_contents=text, file_name="t.txt")
    assert model.file_contents == text.encode("utf-8")
    assert FileModel(file_contents="hello", file_name="t.txt").file_contents == b"hello"


def test_log_model_keeps_cper_list_in_json(tmp_path: Path):
    """CPER-like bytes must not crash log_model and remain in the JSON dump."""
    cper_bytes = b"CPER\x00\x01\xff\xff\xff\xff"
    model = CperListDataModel(
        value="ok",
        cper_data=[FileModel(file_contents=cper_bytes, file_name="corrected-1.cper")],
    )

    model.log_model(str(tmp_path))

    cper_path = tmp_path / "corrected-1.cper"
    assert cper_path.read_bytes() == cper_bytes

    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["value"] == "ok"
    assert len(payload["cper_data"]) == 1
    assert payload["cper_data"][0]["file_name"] == "corrected-1.cper"
    assert base64.urlsafe_b64decode(payload["cper_data"][0]["file_contents"]) == cper_bytes
