# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.

import platform
from typing import Optional

from pydantic import BaseModel, Field

from errorscraper.enums import OSFamily, SystemLocation


class SystemInfo(BaseModel):
    """System object used to store data about System"""

    name: str = platform.node()
    os_family: OSFamily = OSFamily.UNKNOWN
    sku: Optional[str] = None
    platform: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)
    location: Optional[SystemLocation] = SystemLocation.LOCAL
