# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from typing import Optional

from pydantic import BaseModel

from errorscraper.enums import ExecutionStatus


class PluginResult(BaseModel):
    """Object for result of a plugin"""

    status: ExecutionStatus
    source: str
    message: Optional[str] = None
    result_data: Optional[dict | BaseModel] = None
