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
from enum import Enum
from typing import Any, Union

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class ConstraintKey(str, Enum):
    """Keys used in Redfish constraint dicts (e.g. in analyzer checks config).

    Naming aligns with JSON Schema combining: anyOf = value must match any of the list (OR).
    oneOf in JSON Schema means exactly one (XOR); we use anyOf for \"value in allowed list\".
    """

    EQ = "eq"
    MIN = "min"
    MAX = "max"
    ANY_OF = "anyOf"


RedfishConstraint = Union[int, float, str, bool, dict[str, Any]]


class RedfishEndpointAnalyzerArgs(AnalyzerArgs):
    """Analyzer args for config-driven Redfish checks."""

    checks: dict[str, dict[str, RedfishConstraint]] = Field(
        default_factory=dict,
        description=(
            "Map: URI or '*' -> { property_path: constraint }. "
            "URI keys must match a key in the collected responses (exact match). "
            "Use '*' as the key to apply the inner constraints to every collected response body. "
            "Property paths use '/' for nesting and indices, e.g. 'Status/Health', 'PowerControl/0/PowerConsumedWatts'. "
            "Constraints: "
            "'eq' — value must equal the given literal (int, float, str, bool). "
            "'min' — value must be numeric and >= the given number. "
            "'max' — value must be numeric and <= the given number. "
            "'anyOf' — value must be in the given list (OR; any match passes). "
            'Example: { "/redfish/v1/Systems/1": { "Status/Health": { "anyOf": ["OK", "Warning"] }, "PowerState": "On" }, "*": { "Status/Health": { "anyOf": ["OK"] } } }.'
        ),
    )
