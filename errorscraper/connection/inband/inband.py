# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
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
