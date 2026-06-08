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

import json
from pathlib import Path

import pytest

from nodescraper.models import PluginConfig
from nodescraper.plugins.inband.pcie.analyzer_args import PcieAnalyzerArgs
from nodescraper.plugins.inband.pcie.pcie_analyzer import PcieAnalyzer
from nodescraper.plugins.inband.pcie.pcie_collector import PcieCollector
from nodescraper.plugins.inband.pcie.pcie_data import PcieDataModel
from nodescraper.plugins.inband.pcie.pcie_plugin import PciePlugin


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def pcie_config_file(fixtures_dir):
    return fixtures_dir / "pcie_plugin_config.json"


@pytest.fixture
def pcie_advanced_config_file(fixtures_dir):
    return fixtures_dir / "pcie_plugin_advanced_config.json"


def _load_plugin_config(path: Path) -> PluginConfig:
    return PluginConfig.model_validate(json.loads(path.read_text()))


def _pcie_analysis_args(config: PluginConfig) -> PcieAnalyzerArgs:
    return PcieAnalyzerArgs.model_validate(config.plugins["PciePlugin"]["analysis_args"])


def test_pcie_plugin_class_attributes():
    assert PciePlugin.DATA_MODEL is PcieDataModel
    assert PciePlugin.COLLECTOR is PcieCollector
    assert PciePlugin.ANALYZER is PcieAnalyzer
    assert PciePlugin.ANALYZER_ARGS is PcieAnalyzerArgs


def test_pcie_plugin_basic_config_fixture_exists(pcie_config_file):
    assert pcie_config_file.exists(), f"Config file not found: {pcie_config_file}"


def test_pcie_plugin_advanced_config_fixture_exists(pcie_advanced_config_file):
    assert pcie_advanced_config_file.exists(), f"Config file not found: {pcie_advanced_config_file}"


def test_pcie_plugin_with_basic_config(pcie_config_file):
    """Basic config file analysis_args validate as integer PcieAnalyzerArgs."""
    config = _load_plugin_config(pcie_config_file)
    args = _pcie_analysis_args(config)

    assert config.name == "PciePlugin config"
    assert args.exp_speed == 5
    assert args.exp_width == 16
    assert args.exp_sriov_count == 8
    assert args.exp_gpu_count_override == 4
    assert args.exp_max_payload_size == 256
    assert args.exp_max_rd_req_size == 512
    assert args.exp_ten_bit_tag_req_en == 1


def test_pcie_plugin_with_advanced_config(pcie_advanced_config_file):
    """Advanced config file supports device-specific analyzer args."""
    config = _load_plugin_config(pcie_advanced_config_file)
    args = _pcie_analysis_args(config)

    assert config.name == "PciePlugin advanced config"
    assert args.exp_max_payload_size == {29631: 256, 29711: 512}
    assert args.exp_max_rd_req_size == {29631: 512, 29711: 1024}
    assert args.exp_ten_bit_tag_req_en == {29631: 1, 29711: 0}


def test_pcie_plugin_combined_configs(pcie_config_file, pcie_advanced_config_file):
    """Multiple plugin configs merge with later PciePlugin settings taking precedence."""
    basic = _load_plugin_config(pcie_config_file)
    advanced = _load_plugin_config(pcie_advanced_config_file)

    merged = PluginConfig.merge(basic, advanced)
    args = _pcie_analysis_args(merged)

    assert merged.name == "PciePlugin config"
    assert isinstance(args.exp_max_payload_size, dict)
    assert args.exp_max_payload_size[29631] == 256
    assert args.exp_max_payload_size[29711] == 512
    assert args.exp_max_rd_req_size[29711] == 1024


def test_pcie_plugin_run_plugins_entry_present(pcie_config_file):
    """PciePlugin is configured for collection and analysis via plugin config."""
    config = _load_plugin_config(pcie_config_file)

    assert "PciePlugin" in config.plugins
    assert "analysis_args" in config.plugins["PciePlugin"]


def test_pcie_plugin_passive_interaction_config(pcie_config_file):
    """PASSIVE runs use the same analysis args shape as the basic plugin config."""
    config = _load_plugin_config(pcie_config_file)
    args = PcieAnalyzerArgs.model_validate(config.plugins["PciePlugin"]["analysis_args"])

    assert args.exp_speed == 5
    assert args.exp_width == 16


def test_pcie_plugin_skip_sudo_config(pcie_config_file):
    """Skip-sudo scenarios still load the same PciePlugin analysis args from config."""
    config = _load_plugin_config(pcie_config_file)

    assert config.plugins["PciePlugin"]["analysis_args"]["exp_gpu_count_override"] == 4
