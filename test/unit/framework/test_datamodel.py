# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from nodescraper.models.datamodel import DataModel, FileModel


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


class FileHolderModel(DataModel):
    single: FileModel
    many: list[FileModel] = []


def test_file_model_dump_excludes_contents():
    """Binary contents must not be serialized by model_dump_json."""
    fm = FileModel(file_name="a.bin", file_contents=b"CPER\x00\x01\xff\xff\xff\xff")

    assert json.loads(fm.model_dump_json()) == {"file_name": "a.bin"}


def test_file_model_to_file_writes_raw_bytes(tmp_path: Path):
    payload = b"CPER\x00\x01\xff\xff\xff\xff"
    FileModel(file_name="sub/dir/a.bin", file_contents=payload).to_file(str(tmp_path))

    assert (tmp_path / "sub" / "dir" / "a.bin").read_bytes() == payload


def test_data_model_log_model_writes_file_models_separately(tmp_path: Path):
    """Single and list FileModel fields are written as files and don't break the JSON dump."""
    payload = b"CPER\x00\x01\xff\xff\xff\xff"
    model = FileHolderModel(
        single=FileModel(file_name="one.bin", file_contents=payload),
        many=[FileModel(file_name="d/two.bin", file_contents=payload)],
    )

    model.log_model(str(tmp_path))

    assert (tmp_path / "one.bin").read_bytes() == payload
    assert (tmp_path / "d" / "two.bin").read_bytes() == payload
    dumped = json.loads((tmp_path / "fileholdermodel.json").read_text(encoding="utf-8"))
    assert dumped == {"single": {"file_name": "one.bin"}, "many": [{"file_name": "d/two.bin"}]}


def test_file_model_contents_conversion():
    """str and BytesIO contents are converted to bytes, bytes are kept as is."""
    assert FileModel(file_name="a", file_contents="text").file_contents == b"text"
    assert (
        FileModel(file_name="a", file_contents="h\u00e9llo").file_contents == "h\u00e9llo".encode()
    )
    assert FileModel(file_name="a", file_contents=io.BytesIO(b"io")).file_contents == b"io"
    assert FileModel(file_name="a", file_contents=b"\x00\xff").file_contents == b"\x00\xff"


def test_file_model_contents_default_empty():
    assert FileModel(file_name="a").file_contents == b""


def test_file_model_contents_str():
    assert FileModel(file_name="a", file_contents="h\u00e9llo").file_contents_str() == "h\u00e9llo"
    with pytest.raises(UnicodeDecodeError):
        FileModel(file_name="a", file_contents=b"\xff\xfe").file_contents_str()


def test_file_model_requires_file_name():
    with pytest.raises(ValueError):
        FileModel(file_contents=b"x")  # type: ignore[call-arg]


def test_file_model_log_model_is_to_file_alias(tmp_path: Path):
    FileModel(file_name="x/a.log", file_contents=b"data").log_model(str(tmp_path))

    assert (tmp_path / "x" / "a.log").read_bytes() == b"data"


def test_file_model_to_file_overwrites_existing(tmp_path: Path):
    (tmp_path / "a.log").write_bytes(b"old contents that are longer")

    FileModel(file_name="a.log", file_contents=b"new").to_file(str(tmp_path))

    assert (tmp_path / "a.log").read_bytes() == b"new"


def test_file_model_to_file_creates_missing_log_path(tmp_path: Path):
    FileModel(file_name="a.log", file_contents=b"data").to_file(str(tmp_path / "not" / "yet"))

    assert (tmp_path / "not" / "yet" / "a.log").read_bytes() == b"data"


def test_file_model_nested_file_name_stays_in_log_path(tmp_path: Path):
    FileModel(file_name="./sub/dir/nested.log", file_contents=b"ok").to_file(str(tmp_path))

    assert (tmp_path / "sub" / "dir" / "nested.log").read_bytes() == b"ok"


@pytest.mark.parametrize(
    "file_name",
    ["../escaped.log", "sub/../../escaped.log", "{abs_target}", "..", ".", ""],
)
def test_file_model_cannot_escape_log_path(tmp_path: Path, file_name: str):
    base = tmp_path / "logs"
    base.mkdir()
    abs_target = tmp_path / "abs_escaped.log"
    file_name = file_name.format(abs_target=abs_target)

    with pytest.raises(ValueError, match="outside of"):
        FileModel(file_name=file_name, file_contents=b"nope").to_file(str(base))

    assert list(base.iterdir()) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["logs"]


def test_file_model_cannot_escape_log_path_via_symlink(tmp_path: Path):
    base = tmp_path / "logs"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (base / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside of"):
        FileModel(file_name="link/escaped.log", file_contents=b"nope").to_file(str(base))

    assert list(outside.iterdir()) == []


def test_data_model_log_model_rejects_escaping_file_model(tmp_path: Path):
    base = tmp_path / "logs"
    base.mkdir()
    model = FileHolderModel(
        single=FileModel(file_name="../escaped.log", file_contents=b"nope"),
    )

    with pytest.raises(ValueError, match="outside of"):
        model.log_model(str(base))

    assert list(base.iterdir()) == []
    assert not (tmp_path / "escaped.log").exists()
