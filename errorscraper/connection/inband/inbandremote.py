# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
import os
import socket

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    SSHException,
)

from .inband import CommandArtifact, FileArtifact, InBandConnection
from .sshparams import SSHConnectionParams


class SSHConnectionError(Exception):
    """A general exception for ssh connection failures"""


class RemoteShell(InBandConnection):
    """Utility class for running shell commands"""

    def __init__(
        self,
        ssh_params: SSHConnectionParams,
    ) -> None:
        self.ssh_params = ssh_params
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect_ssh(self):
        try:
            self.client.connect(
                hostname=str(self.ssh_params.hostname),
                port=self.ssh_params.port,
                username=self.ssh_params.username,
                password=(
                    self.ssh_params.password.get_secret_value()
                    if self.ssh_params.password
                    else None
                ),
                key_filename=self.ssh_params.key_filename,
                pkey=self.ssh_params.pkey,
                timeout=10,
                look_for_keys=True,
                auth_timeout=60,
                banner_timeout=200,
            )
        except socket.timeout:
            raise SSHConnectionError("SSH Request timeout") from socket.timeout
        except socket.gaierror:
            raise SSHConnectionError("Hostname could not be resolved") from socket.gaierror
        except AuthenticationException:
            raise SSHConnectionError(" SSH Authentication failed") from AuthenticationException
        except BadHostKeyException:
            raise SSHConnectionError("Unable to verify server's host key") from BadHostKeyException
        except ConnectionResetError:
            raise SSHConnectionError("Connection reset by peer") from ConnectionResetError
        except SSHException:
            raise SSHConnectionError("Unable to establish SSH connection") from SSHException
        except EOFError:
            raise SSHConnectionError("EOFError during SSH connection") from EOFError
        except Exception as e:
            raise e

    def read_file(
        self,
        filename: str,
        encoding="utf-8",
        strip: bool = True,
    ) -> FileArtifact:
        """Read a remote file into a file artifact

        Args:
            filename (str): filename
            encoding (str, optional): remote file encoding. Defaults to "utf-8".
            strip (bool): automatically strip file contents

        Returns:
            FileArtifact: file artifact
        """
        contents = ""

        with self.client.open_sftp().open(filename) as remote_file:
            contents = remote_file.read().decode(encoding=encoding, errors="ignore")

        return FileArtifact(
            filename=os.path.interfacesname(filename),
            contents=contents.strip() if strip else contents,
        )

    def run_command(
        self,
        command: str,
        sudo=False,
        timeout: int = 30,
        strip: bool = True,
    ) -> CommandArtifact:
        """Run a shell command over ssh

        Args:
            command (str): command to run
            sudo (bool, optional): run command with sudo (Linux only). Defaults to False.
            timeout (int, optional): timeout for command in seconds. Defaults to 300.
            strip (bool, optional): strip output of command. Defaults to True.

        Returns:
            CommandArtifact: Command artifact with stdout, stderr, which have been decoded and stripped as well as exit code
        """
        write_password = sudo and self.ssh_params.username != "root" and self.ssh_params.password
        if write_password:
            command = f"sudo -S -p '' {command}"
        elif sudo:
            command = f"sudo {command}"

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)

            if write_password:
                stdin.write(
                    self.ssh_params.password.get_secret_value()
                    if self.ssh_params.password
                    else "" + "\n"
                )
                stdin.flush()
                stdin.channel.shutdown_write()

            stdout_str = stdout.read().decode("utf-8")
            stderr_str = stderr.read().decode("utf-8")
            exit_code = stdout.channel.recv_exit_status()
        except TimeoutError:
            stderr_str = "Command timed out"
            stdout_str = ""
            exit_code = 124

        return CommandArtifact(
            command=command,
            stdout=stdout_str.strip() if strip else stdout_str,
            stderr=stderr_str.strip() if strip else stderr_str,
            exit_code=exit_code,
        )
