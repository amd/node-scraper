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
import abc
import os
from typing import Optional

from pydantic import BaseModel


class CommandArtifact(BaseModel):
    """Artifact for the result of shell command execution"""

    command: str
    stdout: str
    stderr: str
    exit_code: int


class BaseFileArtifact(BaseModel, abc.ABC):
    filename: str

    @abc.abstractmethod
    def log_model(self, log_path: str) -> None:
        pass

    @abc.abstractmethod
    def contents_str(self) -> str:
        pass

    @classmethod
    def from_bytes(
        cls,
        filename: str,
        raw_contents: bytes,
        encoding: Optional[str] = "utf-8",
        strip: bool = True,
    ) -> "BaseFileArtifact":
        if encoding is None:
            return BinaryFileArtifact(filename=filename, contents=raw_contents)

        try:
            text = raw_contents.decode(encoding)
            return TextFileArtifact(filename=filename, contents=text.strip() if strip else text)
        except UnicodeDecodeError:
            return BinaryFileArtifact(filename=filename, contents=raw_contents)


class TextFileArtifact(BaseFileArtifact):
    contents: str

    def log_model(self, log_path: str) -> None:
        path = os.path.join(log_path, self.filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.contents)

    def contents_str(self) -> str:
        return self.contents


class BinaryFileArtifact(BaseFileArtifact):
    contents: bytes

    def log_model(self, log_path: str) -> None:
        log_name = os.path.join(log_path, self.filename)
        with open(log_name, "wb") as f:
            f.write(self.contents)

    def contents_str(self) -> str:
        try:
            return self.contents.decode("utf-8")
        except UnicodeDecodeError:
            return f"<binary data: {len(self.contents)} bytes>"


class InBandConnection(abc.ABC):

    @abc.abstractmethod
    def run_command(
        self, command: str, sudo: bool = False, timeout: int = 300, strip: bool = True
    ) -> CommandArtifact:
        """Run an in band shell command

        Args:
            command (str): command to run
            sudo (bool, optional): run command with sudo (Linux only). Defaults to False.
            timeout (int, optional): timeout for command in seconds. Defaults to 300.
            strip (bool, optional): strip output of command. Defaults to True.

        Returns:
            CommandArtifact: command result object
        """

    @abc.abstractmethod
    def read_file(
        self, filename: str, encoding: str = "utf-8", strip: bool = True
    ) -> BaseFileArtifact:
        """Read a file into a BaseFileArtifact

        Args:
            filename (str): filename
            encoding (str, optional): encoding to use when opening file. Defaults to "utf-8".
            strip (bool): automatically strip file contents

        Returns:
            BaseFileArtifact: file artifact
        """
