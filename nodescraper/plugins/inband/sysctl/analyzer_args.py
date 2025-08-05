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

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.sysctl.sysctldata import SysctlDataModel


class SysctlAnalyzerArgs(AnalyzerArgs):
    exp_vm_swappiness: Optional[int] = None
    exp_vm_numa_balancing: Optional[int] = None
    exp_vm_oom_kill_allocating_task: Optional[int] = None
    exp_vm_compaction_proactiveness: Optional[int] = None
    exp_vm_compact_unevictable_allowed: Optional[int] = None
    exp_vm_extfrag_threshold: Optional[int] = None
    exp_vm_zone_reclaim_mode: Optional[int] = None
    exp_vm_dirty_background_ratio: Optional[int] = None
    exp_vm_dirty_ratio: Optional[int] = None
    exp_vm_dirty_writeback_centisecs: Optional[int] = None
    exp_kernel_numa_balancing: Optional[int] = None

    @classmethod
    def build_from_model(cls, datamodel: SysctlDataModel) -> "SysctlAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (SysctlDataModel): data model for plugin

        Returns:
            SysctlAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_vm_swappiness=datamodel.vm_swappiness)
