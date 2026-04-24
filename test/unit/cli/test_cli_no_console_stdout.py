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

import io
import json
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.cli.cli import main


def _assert_main_leaves_stdout_empty(argv: list[str]) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        with pytest.raises(SystemExit) as exc:
            main(argv)
    assert out.getvalue() == "", f"Unexpected stdout: {out.getvalue()!r}"
    code = exc.value.code
    if code is None:
        code = 0
    assert code in (0, 1), f"Unexpected exit code: {exc.value.code!r}"


@pytest.fixture
def no_console_base(tmp_path):
    log_base = tmp_path / "logs"
    log_base.mkdir(parents=True, exist_ok=True)
    return ["--log-path", str(log_base), "--no-console-log", "--log-level", "ERROR"]


def test_describe_no_stdout(no_console_base):
    _assert_main_leaves_stdout_empty(
        no_console_base + ["describe", "plugin", "BiosPlugin"],
    )


def test_summary_no_stdout(no_console_base, tmp_path):
    search = tmp_path / "search_here"
    search.mkdir()
    _assert_main_leaves_stdout_empty(
        no_console_base + ["summary", "--search-path", str(search)],
    )


def test_gen_plugin_config_no_stdout(no_console_base, tmp_path):
    out_dir = tmp_path / "cfg_out"
    out_dir.mkdir()
    _assert_main_leaves_stdout_empty(
        no_console_base
        + [
            "gen-plugin-config",
            "--plugins",
            "BiosPlugin",
            "--output-path",
            str(out_dir),
            "--config-name",
            "out_config.json",
        ],
    )


def test_compare_runs_no_stdout(no_console_base, tmp_path):
    d1 = tmp_path / "run_a"
    d2 = tmp_path / "run_b"
    d1.mkdir()
    d2.mkdir()
    _assert_main_leaves_stdout_empty(
        no_console_base + ["compare-runs", str(d1), str(d2)],
    )


def test_run_plugins_empty_config_no_stdout(no_console_base, tmp_path):
    cfg = tmp_path / "empty_plugins.json"
    cfg.write_text(
        json.dumps(
            {
                "name": "empty",
                "desc": "",
                "plugins": {},
                "global_args": {},
                "result_collators": {},
            }
        ),
        encoding="utf-8",
    )
    _assert_main_leaves_stdout_empty(
        no_console_base + ["run-plugins", f"--plugin-configs={cfg}"],
    )


@patch("nodescraper.cli.cli.get_oem_diagnostic_allowable_values", return_value=["DiagTypeA"])
@patch("nodescraper.cli.cli.RedfishConnection")
def test_show_redfish_oem_allowable_no_stdout(
    mock_conn_cls,
    _mock_get_allowable,
    no_console_base,
    tmp_path,
):
    conn_path = tmp_path / "conn.json"
    conn_path.write_text(
        json.dumps(
            {
                "RedfishConnectionManager": {
                    "host": "127.0.0.1",
                    "username": "u",
                    "password": "p",
                    "verify_ssl": False,
                }
            }
        ),
        encoding="utf-8",
    )
    mock_inst = MagicMock()
    mock_conn_cls.return_value = mock_inst

    _assert_main_leaves_stdout_empty(
        no_console_base
        + [
            "--connection-config",
            str(conn_path),
            "show-redfish-oem-allowable",
            "--log-service-path",
            "redfish/v1/Systems/1/LogServices/Logs",
        ],
    )
    mock_inst._ensure_session.assert_called_once()
    mock_inst.close.assert_called_once()
