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
from pydantic import BaseModel, Field, field_validator


class RedfishEndpointCollectorArgs(BaseModel):
    """Collection args: uris to GET (or discover from tree), optional concurrency and tree discovery."""

    uris: list[str] = Field(
        default_factory=list,
        description="Redfish URIs to GET. Ignored when discover_tree is True.",
    )
    discover_tree: bool = Field(
        default=False,
        description="If True, discover endpoints from the BMC Redfish tree (service root and links) instead of using uris.",
    )
    tree_max_depth: int = Field(
        default=2,
        ge=1,
        le=10,
        description="When discover_tree is True: max traversal depth (1=service root only, 2=root + collections, 3=+ members).",
    )
    tree_max_endpoints: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description="When discover_tree is True: max endpoints to discover (0=no limit).",
    )
    max_workers: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Max concurrent GETs (1=sequential). Use >1 for async endpoint fetches.",
    )

    @field_validator("uris", mode="before")
    @classmethod
    def strip_uris(cls, v: list[str]) -> list[str]:
        """Strip whitespace from each URI in the list."""
        if not v:
            return v
        return [str(uri).strip() for uri in v]
