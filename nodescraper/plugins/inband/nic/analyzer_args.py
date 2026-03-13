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
from typing import Any, Dict, List, Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class NicAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for niccli/nicctl data, with expected_values keyed by canonical command key."""

    expected_values: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Per-command expected checks keyed by canonical key (see command_to_canonical_key).",
    )
    performance_profile_expected: str = Field(
        default="RoCE",
        description="Expected Broadcom performance_profile value (case-insensitive). Default RoCE.",
    )
    support_rdma_disabled_values: List[str] = Field(
        default_factory=lambda: ["0", "false", "disabled", "no", "off"],
        description="Values that indicate RDMA is not supported (case-insensitive).",
    )
    pcie_relaxed_ordering_expected: str = Field(
        default="enabled",
        description="Expected Broadcom pcie_relaxed_ordering value (e.g. 'Relaxed ordering = enabled'); checked case-insensitively. Default enabled.",
    )
    # Expected QoS from niccli getqos (priorities, PFC, ETS) — applied across all adapters when set.
    expected_qos_prio_map: Optional[Dict[Any, Any]] = Field(
        default=None,
        description="Expected priority-to-TC map (e.g. {0: 0, 1: 1}; keys may be int or str in config). Checked per device when set.",
    )
    expected_qos_pfc_enabled: Optional[int] = Field(
        default=None,
        description="Expected PFC enabled value (0/1 or bitmask). Checked per device when set.",
    )
    expected_qos_tsa_map: Optional[Dict[Any, Any]] = Field(
        default=None,
        description="Expected TSA map for ETS (e.g. {0: 'ets', 1: 'strict'}; keys may be int or str in config). Checked per device when set.",
    )
    expected_qos_tc_bandwidth: Optional[List[int]] = Field(
        default=None,
        description="Expected TC bandwidth percentages. Checked per device when set.",
    )
    require_qos_consistent_across_adapters: bool = Field(
        default=True,
        description="When True and no expected_qos_* are set, require all adapters to have the same prio_map, pfc_enabled, and tsa_map.",
    )
    nicctl_log_error_regex: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional list of error patterns for nicctl show card logs."
    )
