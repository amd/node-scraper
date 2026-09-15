###############################################################################
#
# MIT License
#
###############################################################################
from typing import List, Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class NetworkAnalyzerArgs(AnalyzerArgs):
    """Arguments for network and ethtool analysis."""

    expected_nic_firmware: Optional[str] = Field(
        default=None,
        description="Exact firmware version expected from each collected NIC.",
    )
    exclusion_regex: Optional[List[str]] = Field(
        default=None,
        description="Regex patterns matched against interface names before analysis.",
    )
