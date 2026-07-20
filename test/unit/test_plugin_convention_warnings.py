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
import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / ".github" / "scripts" / "plugin_convention_warnings.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("plugin_convention_warnings", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _check_source(src: str, rel_path: str = "example_collector.py") -> list[str]:
    tree = ast.parse(src)
    return checker._check_shell_quoting(Path(rel_path), tree)


def test_shell_quote_rule_flags_args_in_f_string():
    src = """
class ExampleCollector:
    def collect_data(self, args):
        self._run_sut_cmd(f"ping {args.url}")
"""
    msgs = _check_source(src)
    assert len(msgs) == 1
    assert "shell_quote" in msgs[0]
    assert "args.url" in msgs[0]


def test_shell_quote_rule_flags_unquoted_format_kwarg():
    src = """
class ExampleCollector:
    CMD_TMPL = "grep . -H -r -i {rocm_path}/.info/*"

    def collect_data(self, args):
        self._run_sut_cmd(self.CMD_TMPL.format(rocm_path=args.rocm_path))
"""
    msgs = _check_source(src)
    assert len(msgs) == 1
    assert "args.rocm_path" in msgs[0]


def test_shell_quote_rule_allows_quoted_format_kwarg():
    src = """
class ExampleCollector:
    CMD_TMPL = "grep . -H -r -i {rocm_path}/.info/*"

    def collect_data(self, args):
        rocm_path_q = shell_quote(args.rocm_path)
        self._run_sut_cmd(self.CMD_TMPL.format(rocm_path=rocm_path_q))
"""
    assert _check_source(src) == []


def test_shell_quote_rule_allows_inline_shell_quote():
    src = """
class ExampleCollector:
    def _get_afid(self, cper_file_path):
        cmd = self.CMD_RAS_AFID.format(cper_file=shell_quote(cper_file_path))
        self._run_amd_smi(cmd)
"""
    assert _check_source(src) == []


def test_shell_quote_rule_flags_sensitive_function_parameter():
    src = """
class ExampleCollector:
    def _probe(self, url):
        self._run_sut_cmd(f"curl {url}")
"""
    msgs = _check_source(src)
    assert len(msgs) == 1
    assert "url" in msgs[0]


def test_shell_quote_rule_ignores_internal_cmd_parameter():
    src = """
class ExampleCollector:
    def _run_amd_smi(self, cmd):
        self._run_sut_cmd(f"{self.AMD_SMI_EXE} {cmd}")
"""
    assert _check_source(src) == []


def test_shell_quote_rule_flags_reassigned_cmd_variable():
    src = """
class ExampleCollector:
    CMD = "journalctl --no-pager"

    def read(self, args):
        cmd = self.CMD
        if args is not None and args.boot:
            cmd = f"{self.CMD} -b {args.boot}"
        self._run_sut_cmd(cmd, sudo=True)
"""
    msgs = _check_source(src)
    assert len(msgs) == 1
    assert "args.boot" in msgs[0]


def test_shell_quote_rule_skips_generic_collection_collector():
    src = """
class GenericCollectionCollector:
    def collect_data(self, args):
        for cmd_spec in args.commands:
            command = cmd_spec.command.strip()
            self._run_sut_cmd(command)
"""
    assert _check_source(src) == []


def test_shell_quote_rule_allows_system_derived_values():
    src = """
class ExampleCollector:
    def collect(self, iface):
        cmd = self.CMD_ETHTOOL_TEMPLATE.format(interface=iface.name)
        self._run_sut_cmd(cmd, sudo=True)
"""
    assert _check_source(src) == []


@pytest.mark.parametrize(
    "collector_file",
    [
        "nodescraper/plugins/inband/network/network_collector.py",
        "nodescraper/plugins/inband/rocm/rocm_collector.py",
        "nodescraper/plugins/inband/amdsmi/amdsmi_collector.py",
    ],
)
def test_fixed_collectors_have_no_shell_quote_warnings(collector_file):
    path = _REPO_ROOT / collector_file
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(_REPO_ROOT)
    msgs = checker._check_shell_quoting(rel, tree)
    assert msgs == []
