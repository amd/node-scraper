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


class NicCliAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for niccli/nicctl data, with expected_values keyed by canonical command key.

    Use expected_values to compare what each command returned (success or parsed
    content) against desired values. Keys are canonical keys from the data model
    (see niccli_data.command_to_canonical_key), e.g.:
      - nicctl_show_card_json
      - nicctl_show_dcqcn_card_0_json
      - niccli_list

    Each value is a dict of checks the analyzer can apply. Common patterns:
      - require_success: true  -> command must have exit_code 0
      - min_cards: 1          -> for card list, require at least N cards (list length)
      - <field>: <value>      -> require parsed payload to have field equal to value
    """

    expected_values: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Per-command expected checks keyed by canonical key (see command_to_canonical_key).",
    )
