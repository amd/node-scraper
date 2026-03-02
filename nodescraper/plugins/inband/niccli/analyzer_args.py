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
from typing import Any, Dict, Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class NicAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for niccli/nicctl data, with expected_values keyed by canonical command key.

    Use expected_values to define checks; the analyzer uses the data model's
    structured fields (card_show, cards, port, lif, qos, etc.) and results to
    run them. Keys are canonical keys (see nic_data.command_to_canonical_key), e.g.:
      - nicctl_show_card_json
      - nicctl_show_dcqcn_card_0_json
      - niccli_list

    Each value is a dict of checks the analyzer can apply. Common patterns:
      - require_success: true  -> command must have exit_code 0 (from results)
      - min_cards: 1           -> require at least N cards (from cards)
      - <field>: <value>       -> require structured payload to have field equal to value
    """

    expected_values: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Per-command expected checks keyed by canonical key (see command_to_canonical_key).",
    )
