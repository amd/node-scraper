###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from pydantic import BaseModel, field_serializer

from nodescraper.models import DataModel
from nodescraper.utils import bytes_to_human_readable


class DeviceStorageData(BaseModel):
    total: int
    free: int
    used: int
    percent: float

    @field_serializer("total")
    def serialize_total(self, total: int, _info) -> str:
        return bytes_to_human_readable(total)

    @field_serializer("free")
    def serialize_free(self, free: int, _info) -> str:
        return bytes_to_human_readable(free)

    @field_serializer("used")
    def serialize_used(self, used: int, _info) -> str:
        return bytes_to_human_readable(used)

    @field_serializer("percent")
    def serialize_percent(self, percent: float, _info) -> str:
        return f"{percent}%"


class StorageDataModel(DataModel):
    storage_data: dict[str, DeviceStorageData]
