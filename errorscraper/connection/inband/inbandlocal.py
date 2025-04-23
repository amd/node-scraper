# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import os
import subprocess

from .inband import CommandArtifact, FileArtifact, InBandConnection


class LocalShell(InBandConnection):

    def run_command(
        self, command: str, sudo: bool = False, timeout: int = 300, strip: bool = True
    ) -> CommandArtifact:
        """Run a local in band shell command

        Args:
            command (str): command to run
            sudo (bool, optional): run command with sudo (Linux only). Defaults to False.
            timeout (int, optional): timeout for command in seconds. Defaults to 300.
            strip (bool, optional): strip output of command. Defaults to True.

        Returns:
            CommandArtifact: command result object
        """
        if sudo:
            command = f"sudo {command}"

        res = subprocess.run(
            command,
            encoding="utf-8",
            shell=True,
            timeout=timeout,
            capture_output=True,
            check=False,
        )

        return CommandArtifact(
            command=command,
            stdout=res.stdout.strip() if strip else res.stdout,
            stderr=res.stderr.strip() if strip else res.stderr,
            exit_code=res.returncode,
        )

    def read_file(self, filename: str, encoding: str ="utf-8", strip: bool = True) -> FileArtifact:
        """Read a local file into a FileArtifact

        Args:
            filename (str): filename
            encoding (str, optional): encoding to use when opening file. Defaults to "utf-8".
            strip (bool): automatically strip file contents

        Returns:
            FileArtifact: file artifact
        """
        contents = ""
        with open(filename, "r", encoding=encoding) as local_file:
            contents = local_file.read().strip()

        return FileArtifact(
            filename=os.path.basename(filename),
            contents=contents.strip() if strip else contents,
        )
