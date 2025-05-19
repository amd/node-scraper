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
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
import abc

from pydantic import BaseModel


class CommandArtifact(BaseModel):
    """Artifact for the result of shell command execution"""

    command: str
    stdout: str
    stderr: str
    exit_code: int


class FileArtifact(BaseModel):
    """Artifact to contains contents of file read into memory"""

    filename: str
    contents: str


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
    def read_file(self, filename: str, encoding: str = "utf-8", strip: bool = True) -> FileArtifact:
        """Read a file into a FileArtifact

        Args:
            filename (str): filename
            encoding (str, optional): encoding to use when opening file. Defaults to "utf-8".
            strip (bool): automatically strip file contents

        Returns:
            FileArtifact: file artifact
        """
