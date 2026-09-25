###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from typing import Optional

from pydantic import Field

from nodescraper.models import AnalyzerArgs


class NvmeAnalyzerArgs(AnalyzerArgs):
    maximum_smart_error_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum allowed NVMe SMART media error count per device.",
    )
