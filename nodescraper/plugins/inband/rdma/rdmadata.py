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
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

from nodescraper.models import DataModel


class RdmaStatistics(BaseModel):
    """RDMA statistic entry from 'rdma statistic -j'."""

    ifname: Optional[str] = None
    port: Optional[int] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be set in RdmaStatistics")
        return self


class RdmaLink(BaseModel):
    """RDMA link entry from 'rdma link -j'."""

    ifindex: Optional[int] = None
    ifname: Optional[str] = None
    port: Optional[int] = None
    state: Optional[str] = None
    physical_state: Optional[str] = None
    netdev: Optional[str] = None
    netdev_index: Optional[int] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be set in RdmaLink")
        return self


class RdmaDataModel(DataModel):
    """
    Data model for RDMA (Remote Direct Memory Access) statistics and link information.

    Attributes:
        statistic_list: List of RDMA statistics from 'rdma statistic -j'.
        link_list: List of RDMA links from 'rdma link -j'.
    """

    link_list: list[RdmaLink] = Field(default_factory=list)
    statistic_list: list[RdmaStatistics] = Field(default_factory=list)
