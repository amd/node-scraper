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
from unittest.mock import MagicMock, patch

from nodescraper.connection.inband.inbandlocal import LocalShell


@patch("nodescraper.connection.inband.inbandlocal.subprocess.run")
def test_localshell_string_uses_shell_true(mock_run):
    mock_run.return_value = MagicMock(stdout="ok\n", stderr="", returncode=0)

    shell = LocalShell()
    shell.run_command("ip addr show")

    assert mock_run.call_args.kwargs["shell"] is True


@patch("nodescraper.connection.inband.inbandlocal.subprocess.run")
def test_localshell_string_with_sudo(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

    shell = LocalShell()
    shell.run_command("cat /etc/shadow", sudo=True)

    assert mock_run.call_args.args[0] == "sudo cat /etc/shadow"
