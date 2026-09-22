# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import json
import os
from pathlib import Path

from nodescraper.models.datamodel import DataModel


class FolderDataModel(DataModel):
    value: str = ""

    @classmethod
    def build_from_folder(cls, folder_path: str) -> "FolderDataModel":
        return cls(value=os.path.basename(folder_path))


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
