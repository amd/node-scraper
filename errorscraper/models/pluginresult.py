# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from typing import Optional

from pydantic import BaseModel

from errorscraper.enums import ExecutionStatus


class PluginResult(BaseModel):
    """Object for result of a task"""

    status: ExecutionStatus
    result_data: Optional[BaseModel] = None
