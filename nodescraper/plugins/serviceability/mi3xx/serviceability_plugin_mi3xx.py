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
from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)
from nodescraper.plugins.serviceability.serviceability_plugin_base import (
    ServiceabilityPluginBase,
)
from nodescraper.utils import register_log_dir_name

from .mi3xx_analyzer import MI3XXAnalyzer
from .mi3xx_collector import MI3XXCollector
from .mi3xx_collector_args import MI3XXCollectorArgs

register_log_dir_name("ServiceabilityPluginMI3XX", "serviceability_plugin_MI3XX")
register_log_dir_name("MI3XXCollector", "MI3XX_collector")
register_log_dir_name("MI3XXAnalyzer", "MI3XX_analyzer")


class ServiceabilityPluginMI3XX(ServiceabilityPluginBase):
    """MI3XX OOB Redfish serviceability: BMC event log, CPER attachments, and service hub analysis."""

    DATA_MODEL = ServiceabilityDataModel
    COLLECTOR = MI3XXCollector
    ANALYZER = MI3XXAnalyzer
    COLLECTOR_ARGS = MI3XXCollectorArgs
    ANALYZER_ARGS = ServiceabilityAnalyzerArgs
