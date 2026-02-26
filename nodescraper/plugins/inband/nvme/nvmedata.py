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
from typing import Optional

from pydantic import BaseModel, Field

from nodescraper.models import DataModel


class NvmeListEntry(BaseModel):
    """One row from 'nvme list': a single NVMe device/namespace line."""

    node: Optional[str] = Field(default=None, description="Device node path (e.g. /dev/nvme0n1).")
    generic: Optional[str] = Field(
        default=None, description="Generic device node (e.g. /dev/ng0n1)."
    )
    serial_number: Optional[str] = Field(default=None, description="Serial number (SN).")
    model: Optional[str] = Field(default=None, description="Model name.")
    namespace_id: Optional[str] = Field(default=None, description="Namespace ID.")
    usage: Optional[str] = Field(default=None, description="Usage (e.g. capacity).")
    format_lba: Optional[str] = Field(
        default=None, description="LBA format (sector size + metadata)."
    )
    fw_rev: Optional[str] = Field(default=None, description="Firmware revision.")


class DeviceNvmeData(BaseModel):
    smart_log: Optional[str] = None
    error_log: Optional[str] = None
    id_ctrl: Optional[str] = None
    id_ns: Optional[str] = None
    fw_log: Optional[str] = None
    self_test_log: Optional[str] = None
    get_log: Optional[str] = None
    telemetry_log: Optional[str] = None


class NvmeDataModel(DataModel):
    """NVMe collection output: parsed 'nvme list' entries and per-device command outputs."""

    nvme_list: Optional[list[NvmeListEntry]] = Field(
        default=None,
        description="Parsed list of NVMe devices from 'nvme list'.",
    )
    devices: dict[str, DeviceNvmeData] = Field(default_factory=dict)
