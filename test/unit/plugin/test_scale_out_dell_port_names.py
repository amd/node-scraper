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
from nodescraper.plugins.inband.switch.scale_out_dell.port_names import (
    normalize_port_token,
    resolve_detail_port_names,
    to_eth_port_name,
)


def test_normalize_port_token_accepts_eth_prefix():
    assert normalize_port_token("Eth1/1/1") == "1/1/1"
    assert normalize_port_token("1/1") == "1/1"


def test_to_eth_port_name_builds_valid_cli_name():
    assert to_eth_port_name("1/1/1") == "Eth1/1/1"
    assert to_eth_port_name("Eth1/1") == "Eth1/1"


def test_to_eth_port_name_rejects_injection():
    assert to_eth_port_name('Eth1"; rm -rf /') is None
    assert to_eth_port_name("not-a-port") is None


def test_resolve_detail_port_names_uses_interface_status_keys():
    status = {"Eth1/1/1": object(), "Eth1/1/2": object()}
    names, invalid = resolve_detail_port_names(["1/1/1", "Eth1/1/2"], status)
    assert invalid is None
    assert names == ["Eth1/1/1", "Eth1/1/2"]


def test_resolve_detail_port_names_falls_back_without_status():
    names, invalid = resolve_detail_port_names(["1/1/1"], None)
    assert invalid is None
    assert names == ["Eth1/1/1"]
