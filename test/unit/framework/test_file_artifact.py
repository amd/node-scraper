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

from pathlib import Path

from nodescraper.connection.inband.inband import (
    BaseFileArtifact,
    BinaryFileArtifact,
    TextFileArtifact,
)


def test_textfileartifact_contents_str():
    artifact = TextFileArtifact(filename="text.txt", contents="hello")
    assert artifact.contents_str() == "hello"


def test_binaryfileartifact_contents_str():
    artifact = BinaryFileArtifact(filename="blob.bin", contents=b"\xff\x00\xab")
    result = artifact.contents_str()
    assert result.startswith("<binary data:")
    assert "bytes>" in result


def test_from_bytes_text():
    artifact = BaseFileArtifact.from_bytes("test.txt", b"simple text", encoding="utf-8")
    assert isinstance(artifact, TextFileArtifact)
    assert artifact.contents == "simple text"


def test_from_bytes_binary():
    artifact = BaseFileArtifact.from_bytes("data.bin", b"\xff\x00\xab", encoding="utf-8")
    assert isinstance(artifact, BinaryFileArtifact)
    assert artifact.contents == b"\xff\x00\xab"


def test_log_model_text(tmp_path: Path):
    artifact = TextFileArtifact(filename="log.txt", contents="some text")
    artifact.log_model(str(tmp_path))
    output_path = tmp_path / "log.txt"
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "some text"


def test_log_model_binary(tmp_path: Path):
    binary_data = b"\x01\x02\xffDATA"
    artifact = BinaryFileArtifact(filename="binary.bin", contents=binary_data)
    artifact.log_model(str(tmp_path))
    output_path = tmp_path / "binary.bin"
    assert output_path.exists()
    assert output_path.read_bytes() == binary_data
