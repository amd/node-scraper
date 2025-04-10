# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.
from typing import Optional

from pydantic import BaseModel

from .datamodel import DataModel
from .taskresult import TaskResult


class DataPluginResult(BaseModel):
    """Object for result of data plugin"""

    system_data: Optional[DataModel] = None
    collection_result: Optional[TaskResult] = None
    analysis_result: Optional[TaskResult] = None
