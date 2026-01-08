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
import argparse
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

import pytest
from pydantic import BaseModel

from nodescraper.base import InBandDataPlugin
from nodescraper.cli import cli, inputargtypes
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import SystemInfo
from nodescraper.pluginregistry import PluginRegistry


def test_log_path_arg():
    assert cli.log_path_arg("test") == "test"
    assert cli.log_path_arg("none") is None


@pytest.mark.parametrize(
    "arg_input, exp_output",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
    ],
)
def test_bool_arg(arg_input, exp_output):
    assert inputargtypes.bool_arg(arg_input) == exp_output


def test_bool_arg_exception():
    with pytest.raises(argparse.ArgumentTypeError):
        inputargtypes.bool_arg("invalid")


def test_dict_arg():
    assert inputargtypes.dict_arg('{"test": 123}') == {"test": 123}
    with pytest.raises(argparse.ArgumentTypeError):
        inputargtypes.dict_arg("invalid")


def test_json_arg(framework_fixtures_path):
    assert cli.json_arg(os.path.join(framework_fixtures_path, "example.json")) == {"test": 123}
    with pytest.raises(argparse.ArgumentTypeError):
        cli.json_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_model_arg(framework_fixtures_path):
    class TestArg(BaseModel):
        test: int

    arg_handler = cli.ModelArgHandler(TestArg)
    assert arg_handler.process_file_arg(
        os.path.join(framework_fixtures_path, "example.json")
    ) == TestArg(test=123)

    with pytest.raises(argparse.ArgumentTypeError):
        arg_handler.process_file_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_system_info_builder():
    assert cli.get_system_info(
        argparse.Namespace(
            sys_name="test_name",
            sys_sku="test_sku",
            sys_platform="test_plat",
            sys_location="LOCAL",
            system_config=None,
        )
    ) == SystemInfo(
        name="test_name", sku="test_sku", platform="test_plat", location=SystemLocation.LOCAL
    )

    with pytest.raises(argparse.ArgumentTypeError):
        cli.get_system_info(
            argparse.Namespace(
                sys_name="test_name",
                sys_sku="test_sku",
                sys_platform="test_plat",
                sys_location="INVALID",
                system_config=None,
            )
        )


@pytest.mark.parametrize(
    "raw_arg_input, plugin_names, exp_output",
    [
        (
            ["--sys-name", "test-sys", "--sys-sku", "test-sku"],
            ["TestPlugin1", "TestPlugin2"],
            (["--sys-name", "test-sys", "--sys-sku", "test-sku"], {}, []),
        ),
        (
            ["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"],
            ["TestPlugin1", "TestPlugin2"],
            (["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"], {}, []),
        ),
        (
            [
                "--sys-name",
                "test-sys",
                "--sys-sku",
                "test-sku",
                "run-plugins",
                "TestPlugin1",
                "--plugin1_arg",
                "test-val1",
                "TestPlugin2",
                "--plugin2_arg",
                "test-val2",
            ],
            ["TestPlugin1", "TestPlugin2"],
            (
                ["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins"],
                {
                    "TestPlugin1": ["--plugin1_arg", "test-val1"],
                    "TestPlugin2": ["--plugin2_arg", "test-val2"],
                },
                [],
            ),
        ),
    ],
)
def test_process_args(raw_arg_input, plugin_names, exp_output):
    assert cli.process_args(raw_arg_input, plugin_names) == exp_output


def test_discover_external_plugins_top_level():
    """Test discovering ext_nodescraper_plugins as a top-level import."""
    mock_ext_pkg = mock.MagicMock()
    mock_ext_pkg.__file__ = "/path/to/ext_nodescraper_plugins/__init__.py"

    with mock.patch("nodescraper.cli.cli.import_module"):
        with mock.patch.dict("sys.modules", {"ext_nodescraper_plugins": mock_ext_pkg}):
            result = cli.discover_external_plugins()

            assert len(result) >= 1
            assert mock_ext_pkg in result


def test_discover_external_plugins_no_plugins():
    """Test when no external plugins are installed."""
    with mock.patch("nodescraper.cli.cli.import_module") as mock_import:
        mock_import.side_effect = ImportError("No module named 'ext_nodescraper_plugins'")

        with mock.patch("importlib.metadata.distributions", return_value=[]):
            result = cli.discover_external_plugins()

            assert result == []


def test_discover_external_plugins_from_installed_package():
    """Test discovering plugins from installed packages (not top-level)."""
    mock_dist = mock.MagicMock()
    mock_dist.metadata.get.return_value = "amd-custom-package"
    mock_dist.read_text.return_value = "custompackage"

    mock_plugin = mock.MagicMock()
    mock_plugin.__file__ = "/path/to/custompackage/ext_nodescraper_plugins/__init__.py"

    def mock_import_func(module_path):
        if module_path == "custompackage.ext_nodescraper_plugins":
            return mock_plugin
        raise ImportError(f"No module named '{module_path}'")

    with mock.patch("nodescraper.cli.cli.import_module", side_effect=mock_import_func):
        with mock.patch("importlib.metadata.distributions", return_value=[mock_dist]):
            result = cli.discover_external_plugins()

            assert mock_plugin in result


def test_discover_external_plugins_deduplication():
    """Test that duplicate plugins are not added multiple times."""
    mock_ext_pkg = mock.MagicMock()
    mock_ext_pkg.__file__ = "/path/to/ext_nodescraper_plugins/__init__.py"

    mock_dist1 = mock.MagicMock()
    mock_dist1.metadata.get.return_value = "package-one"
    mock_dist1.read_text.return_value = "package_one"

    mock_dist2 = mock.MagicMock()
    mock_dist2.metadata.get.return_value = "package-two"
    mock_dist2.read_text.return_value = "package_one"

    def mock_import_func(module_path):
        if "package_one.ext_nodescraper_plugins" in module_path:
            return mock_ext_pkg
        raise ImportError(f"No module named '{module_path}'")

    with mock.patch("nodescraper.cli.cli.import_module", side_effect=mock_import_func):
        with mock.patch("importlib.metadata.distributions", return_value=[mock_dist1, mock_dist2]):
            result = cli.discover_external_plugins()

            file_paths = [pkg.__file__ for pkg in result if hasattr(pkg, "__file__")]
            assert file_paths.count(mock_ext_pkg.__file__) == 1


def test_discover_external_plugins_name_variants():
    """Test that different package name variants are tried (hyphens vs underscores)."""
    mock_dist = mock.MagicMock()
    mock_dist.metadata.get.return_value = "amd-error-scraper"
    mock_dist.read_text.side_effect = Exception("No top_level.txt")

    mock_plugin = mock.MagicMock()
    mock_plugin.__file__ = "/path/to/amd_error_scraper/ext_nodescraper_plugins/__init__.py"

    call_count = {"count": 0}

    def mock_import_func(module_path):
        call_count["count"] += 1
        if module_path == "amd_error_scraper.ext_nodescraper_plugins":
            return mock_plugin
        raise ImportError(f"No module named '{module_path}'")

    with mock.patch("nodescraper.cli.cli.import_module", side_effect=mock_import_func):
        with mock.patch("importlib.metadata.distributions", return_value=[mock_dist]):
            result = cli.discover_external_plugins()

            assert mock_plugin in result
            assert call_count["count"] >= 1


def test_discover_external_plugins_handles_exceptions():
    """Test that discovery continues even if some packages fail."""
    mock_dist1 = mock.MagicMock()
    mock_dist1.metadata.get.return_value = "good-package"
    mock_dist1.read_text.return_value = "goodpackage"

    mock_dist2 = mock.MagicMock()
    mock_dist2.metadata.get.side_effect = Exception("Corrupted metadata")

    mock_plugin = mock.MagicMock()
    mock_plugin.__file__ = "/path/to/goodpackage/ext_nodescraper_plugins/__init__.py"

    def mock_import_func(module_path):
        if module_path == "goodpackage.ext_nodescraper_plugins":
            return mock_plugin
        raise ImportError(f"No module named '{module_path}'")

    with mock.patch("nodescraper.cli.cli.import_module", side_effect=mock_import_func):
        with mock.patch("importlib.metadata.distributions", return_value=[mock_dist1, mock_dist2]):
            result = cli.discover_external_plugins()

            assert mock_plugin in result


def test_external_plugins_integration():
    """Integration test: Create a temporary external plugin and verify it's picked up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "test_external_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        ext_plugins_dir = pkg_dir / "ext_nodescraper_plugins"
        ext_plugins_dir.mkdir()
        (ext_plugins_dir / "__init__.py").write_text("")

        plugin_module_dir = ext_plugins_dir / "test_plugin"
        plugin_module_dir.mkdir()

        plugin_code = """
from nodescraper.base import InBandDataPlugin
from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer

class TestAnalyzer(DataAnalyzer):
    DATA_MODEL = dict

    def analyze_data(self, data):
        return ExecutionStatus.SUCCESS, None

class TestExternalPlugin(InBandDataPlugin):
    DATA_MODEL = dict
    ANALYZER = TestAnalyzer

    def run(self):
        return ExecutionStatus.SUCCESS, {"test": "data"}
"""
        (plugin_module_dir / "__init__.py").write_text(plugin_code)

        sys.path.insert(0, tmpdir)

        try:
            import test_external_pkg.ext_nodescraper_plugins as test_ext_pkg

            plugin_registry = PluginRegistry(plugin_pkg=[test_ext_pkg])

            assert (
                "TestExternalPlugin" in plugin_registry.plugins
            ), f"External plugin not found. Available plugins: {list(plugin_registry.plugins.keys())}"

            plugin_class = plugin_registry.plugins["TestExternalPlugin"]
            assert plugin_class.__name__ == "TestExternalPlugin"

        finally:
            sys.path.remove(tmpdir)
            modules_to_remove = [
                key for key in sys.modules.keys() if key.startswith("test_external_pkg")
            ]
            for module in modules_to_remove:
                del sys.modules[module]


def test_discover_and_load_external_plugins():
    """Test the full flow: discover external plugins using mocked modules."""
    mock_plugin_module = types.ModuleType("mock_ext_nodescraper_plugins")
    mock_plugin_module.__file__ = "/fake/path/mock_ext_nodescraper_plugins/__init__.py"
    mock_plugin_module.__path__ = ["/fake/path/mock_ext_nodescraper_plugins"]

    mock_submodule = types.ModuleType("mock_ext_nodescraper_plugins.mock_plugin")
    mock_submodule.__file__ = "/fake/path/mock_ext_nodescraper_plugins/mock_plugin.py"

    class MockAnalyzer(DataAnalyzer):
        DATA_MODEL = dict

        def analyze_data(self, data):
            return ExecutionStatus.SUCCESS, None

    class MockExternalPlugin(InBandDataPlugin):
        DATA_MODEL = dict
        ANALYZER = MockAnalyzer

        def run(self):
            return ExecutionStatus.SUCCESS, {}

    mock_submodule.MockExternalPlugin = MockExternalPlugin

    def mock_iter_modules(path, prefix=""):
        yield None, f"{prefix}mock_plugin", False

    def mock_import_module(name):
        if "mock_plugin" in name:
            return mock_submodule
        raise ImportError(f"No module named {name}")

    with mock.patch("pkgutil.iter_modules", side_effect=mock_iter_modules):
        with mock.patch("importlib.import_module", side_effect=mock_import_module):
            plugin_registry = PluginRegistry(plugin_pkg=[mock_plugin_module])

            assert "MockExternalPlugin" in plugin_registry.plugins
            assert plugin_registry.plugins["MockExternalPlugin"] == MockExternalPlugin
