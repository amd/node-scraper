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


class ModuleParameter(BaseModel):
    name: str
    type: Optional[str] = None
    description: Optional[str] = None


class ModuleInfo(BaseModel):
    filename: Optional[str] = None
    version: Optional[str] = None
    license: Optional[str] = None
    description: Optional[str] = None
    author: list[str] = Field(default_factory=list)
    firmware: list[str] = Field(default_factory=list)
    srcversion: Optional[str] = None
    depends: list[str] = Field(default_factory=list)
    name: Optional[str] = None
    vermagic: Optional[str] = None
    sig_id: Optional[str] = None
    signer: Optional[str] = None
    sig_key: Optional[str] = None
    sig_hashalgo: Optional[str] = None
    parm: list[ModuleParameter] = Field(default_factory=list)


class KernelModuleDataModel(DataModel):
    kernel_modules: dict
    amdgpu_modinfo: Optional[ModuleInfo] = None
