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
import os
import socket
from typing import Type, Union

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    SSHException,
)

from .inband import (
    BaseFileArtifact,
    CommandArtifact,
    InBandConnection,
)
from .sshparams import SSHConnectionParams


class SSHConnectionError(Exception):
    """A general exception for ssh connection failures"""


CHANNEL_OPEN_TIMEOUT = 60


class RemoteShell(InBandConnection):
    """Utility class for running shell commands"""

    host_key_policy: Type[paramiko.MissingHostKeyPolicy] = paramiko.RejectPolicy
    _proxy_ssh_down: bool = False

    def __init__(
        self,
        ssh_params: SSHConnectionParams,
    ) -> None:
        """Creates a RemoteShell Instance.

        Args:
            ssh_params (SSHConnectionParams): The parameters used to initiate the SSH connection username/password/ect.
        """
        self.ssh_params = ssh_params
        self._new_client()

    def _new_client(self) -> None:
        """Replace the SSH client with a new unconnected client.

        Returns:
            None.
        """
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(self.host_key_policy())

    def _arm_channel_timeout(self) -> None:
        """Bound channel opens that do not pass their own timeout.

        Returns:
            None.
        """
        transport = self.client.get_transport()
        if transport is not None and transport.channel_timeout is None:
            transport.channel_timeout = CHANNEL_OPEN_TIMEOUT

    def connect_ssh(self):
        """Connect to the remote host via SSH"""
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
            self._arm_channel_timeout()
        except socket.timeout:
            raise SSHConnectionError("SSH Request timeout") from socket.timeout
        except socket.gaierror as e:
            raise SSHConnectionError("Hostname could not be resolved") from e
        except AuthenticationException as e:
            raise SSHConnectionError("SSH Authentication failed") from e
        except BadHostKeyException as e:
            raise SSHConnectionError("Unable to verify server's host key") from e
        except ConnectionResetError as e:
            raise SSHConnectionError("Connection reset by peer") from e
        except SSHException as e:
            raise SSHConnectionError(f"Unable to establish SSH connection: {str(e)}") from e
        except EOFError as e:
            raise SSHConnectionError("EOFError during SSH connection") from e
        except Exception as e:
            raise e

    def reconnect_ssh(self) -> None:
        """Close the current SSH session and open a new one.

        Returns:
            None.
        """
        try:
            self.client.close()
        except (OSError, SSHException):
            pass
        self._new_client()
        self.connect_ssh()

    def read_file(
        self,
        filename: str,
        encoding: Union[str, None] = "utf-8",
        strip: bool = True,
    ) -> BaseFileArtifact:
        """Read a remote file into a BaseFileArtifact.

        Args:
            filename (str): Path to file on remote host
            encoding Optional[Union[str, None]]: If None, file is read as binary. If str, decode using that encoding. Defaults to "utf-8".
            strip (bool): Strip whitespace for text files. Ignored for binary.

        Returns:
            BaseFileArtifact: Object representing file contents
        """
        raw_contents = self.read_files([filename])[0]
        return BaseFileArtifact.from_bytes(
            filename=os.path.basename(filename),
            raw_contents=raw_contents,
            encoding=encoding,
            strip=strip,
        )

    def read_files(self, filenames: list[str]) -> list[bytes]:
        """Read remote files through one SFTP session.

        Args:
            filenames: Remote paths to read.

        Returns:
            File contents in the same order as filenames.
        """
        self._arm_channel_timeout()
        sftp = self.client.open_sftp()
        try:
            contents: list[bytes] = []
            for filename in filenames:
                with sftp.open(filename, "rb") as remote_file:
                    contents.append(remote_file.read())
            return contents
        finally:
            sftp.close()

    def run_command(
        self,
        command: str,
        sudo=False,
        timeout: int = 30,
        strip: bool = True,
    ) -> CommandArtifact:
        """Run a shell command over ssh.

        Args:
            command (str): shell command string.
            sudo (bool, optional): run command with sudo (Linux only). Defaults to False.
            timeout (int, optional): timeout for command in seconds. Defaults to 300.
            strip (bool, optional): strip output of command. Defaults to True.

        Returns:
            CommandArtifact: Command artifact with stdout, stderr, which have been decoded and stripped as well as exit code
        """
        write_password = sudo and self.ssh_params.username != "root" and self.ssh_params.password

        cmd_str = command
        if write_password:
            cmd_str = f"sudo -S -p '' {cmd_str}"
        elif sudo:
            cmd_str = f"sudo {cmd_str}"

        channel = None
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd_str, timeout=timeout)
            channel = stdout.channel
            if write_password:
                stdin.write(
                    (
                        self.ssh_params.password.get_secret_value()
                        if self.ssh_params.password
                        else ""
                    )
                    + "\n"
                )
                stdin.flush()
                stdin.channel.shutdown_write()
            stdout_str = stdout.read().decode("utf-8", errors="replace")
            stderr_str = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
        except TimeoutError:
            stderr_str = "Command timed out"
            stdout_str = ""
            exit_code = 124
        except SSHException as exc:
            stderr_str = str(exc) or "SSH channel failed"
            stdout_str = ""
            exit_code = 124
        finally:
            if channel is not None:
                try:
                    channel.close()
                except (OSError, SSHException):
                    pass

        return CommandArtifact(
            command=cmd_str,
            stdout=stdout_str.strip() if strip else stdout_str,
            stderr=stderr_str.strip() if strip else stderr_str,
            exit_code=exit_code,
        )
