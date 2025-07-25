import io

import pytest

from nodescraper.connection.inband.inband import (
    FileArtifact,  # adjust import path accordingly
)


def test_fileartifact_accepts_str_and_encodes():
    artifact = FileArtifact(filename="test.txt", contents="hello")
    assert isinstance(artifact.contents, bytes)
    assert artifact.contents == b"hello"


def test_fileartifact_accepts_bytes():
    artifact = FileArtifact(filename="data.bin", contents=b"\x00\xff")
    assert artifact.contents == b"\x00\xff"


def test_fileartifact_accepts_bytesio():
    artifact = FileArtifact(filename="stream.txt", contents=io.BytesIO(b"abc123"))
    assert artifact.contents == b"abc123"


def test_contents_str_decodes_utf8():
    artifact = FileArtifact(filename="text.txt", contents="hello")
    assert artifact.contents_str() == "hello"


def test_contents_str_handles_binary():
    artifact = FileArtifact(filename="blob.bin", contents=b"\xff\x00\xab")
    result = artifact.contents_str()
    assert result.startswith("<binary data:")
    assert "bytes>" in result


def test_log_model_text(tmp_path):
    artifact = FileArtifact(filename="log.txt", contents="text content")
    artifact.log_model(str(tmp_path), encoding="utf-8")

    out_path = tmp_path / "log.txt"
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8") == "text content"


def test_log_model_binary(tmp_path):
    binary_data = b"\x01\x02\xffDATA"
    artifact = FileArtifact(filename="binary.bin", contents=binary_data)
    artifact.log_model(str(tmp_path), encoding=None)

    out_path = tmp_path / "binary.bin"
    assert out_path.exists()
    assert out_path.read_bytes() == binary_data


def test_log_model_raises_on_invalid_encoding(tmp_path):
    artifact = FileArtifact(filename="bad.txt", contents=b"\xff\xff")
    with pytest.raises(UnicodeDecodeError):
        artifact.log_model(str(tmp_path), encoding="utf-8")
