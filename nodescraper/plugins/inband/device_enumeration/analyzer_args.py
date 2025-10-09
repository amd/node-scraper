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

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.device_enumeration.deviceenumdata import (
    DeviceEnumerationDataModel,
)


class DeviceEnumerationAnalyzerArgs(AnalyzerArgs):
    cpu_count: list | int = (None,)
    gpu_count: list | int = (None,)
    vf_count: list | int = (None,)

    @classmethod
    def build_from_model(
        cls, datamodel: DeviceEnumerationDataModel
    ) -> "DeviceEnumerationAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (DeviceEnumerationDataModel): data model for plugin

        Returns:
            DeviceEnumerationAnalyzerArgs: instance of analyzer args class
        """
        return cls(exp_bios_version=datamodel.bios_version)
