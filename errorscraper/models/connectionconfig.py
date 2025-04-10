# Copyright (C) 2024 Advanced Micro Devices, Inc. All rights reserved.

from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    connection: dict[str, dict] = Field(default_factory=dict)
