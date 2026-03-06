###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
from typing import Optional

from pydantic import BaseModel, Field


class RedfishEndpointCollectorArgs(BaseModel):
    """Collection args: uris to GET, optional config_file path for uris."""

    uris: list[str] = Field(default_factory=list)
    config_file: Optional[str] = None
