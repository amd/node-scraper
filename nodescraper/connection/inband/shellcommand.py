###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from typing import Sequence, Union

from nodescraper.utils import shell_quote

ShellCommand = Union[str, Sequence[str]]


def format_argv_display(argv: Sequence[str]) -> str:
    """Return a shell-safe, human-readable command string for logging/artifacts.

    Args:
        argv (Sequence[str]): argv tokens passed to subprocess or remote shell.

    Returns:
        str: quoted command string suitable for CommandArtifact.command.
    """
    return " ".join(shell_quote(arg) for arg in argv)


def build_exec_argv(argv: Sequence[str], *, sudo: bool = False) -> list[str]:
    """Prepend sudo when requested.

    Args:
        argv (Sequence[str]): base command argv.
        sudo (bool, optional): whether to run with sudo. Defaults to False.

    Returns:
        list[str]: argv for local subprocess.run(shell=False) or remote quoting.
    """
    base = list(argv)
    if sudo:
        return ["sudo", *base]
    return base


def build_sudo_password_argv(argv: Sequence[str]) -> list[str]:
    """Build argv for sudo -S (password on stdin) over SSH.

    Args:
        argv (Sequence[str]): base command argv.

    Returns:
        list[str]: argv prefixed with sudo -S -p ''.
    """
    return ["sudo", "-S", "-p", "", *list(argv)]
