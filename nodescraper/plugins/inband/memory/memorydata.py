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

from pydantic import BaseModel

from nodescraper.models import DataModel


class MemoryBlock(BaseModel):
    """Memory block information from lsmem"""

    range: str
    size: str
    state: str
    removable: Optional[str] = None
    block: Optional[str] = None


class MemorySummary(BaseModel):
    """Summary information from lsmem"""

    memory_block_size: Optional[str] = None
    total_online_memory: Optional[str] = None
    total_offline_memory: Optional[str] = None


class LsmemData(BaseModel):
    """Complete lsmem output data"""

    memory_blocks: list[MemoryBlock]
    summary: MemorySummary


class NumaNode(BaseModel):
    """NUMA node information"""

    node_id: int
    cpus: list[int]
    memory_size_mb: Optional[int] = None
    memory_free_mb: Optional[int] = None


class NumaDistance(BaseModel):
    """Distance between two NUMA nodes"""

    from_node: int
    to_node: int
    distance: int


class NumaTopology(BaseModel):
    """Complete NUMA topology from 'numactl --hardware'"""

    available_nodes: list[int]
    nodes: list[NumaNode]
    distances: list[NumaDistance]
    distance_matrix: Optional[dict[int, dict[int, int]]] = None


class MemoryDataModel(DataModel):
    """Memory data model"""

    mem_free: str
    mem_total: str
    lsmem_data: Optional[LsmemData] = None
    numa_topology: Optional[NumaTopology] = None
