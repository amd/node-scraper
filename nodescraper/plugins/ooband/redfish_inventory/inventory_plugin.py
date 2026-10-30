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
from nodescraper.base import OOBandDataPlugin
from nodescraper.connection.redfish import RedfishSshProxyConnectionManager

from .collector_args import RedfishInventoryCollectorArgs
from .inventory_collector import RedfishInventoryCollector
from .inventory_data import RedfishInventoryDataModel


class RedfishInventoryPlugin(
    OOBandDataPlugin[RedfishInventoryDataModel, RedfishInventoryCollectorArgs, None]
):
    """Collect portable BMC and SMC Redfish inventory over the native Redfish connection.

    BMC coverage is Chassis, Managers, Assembly, PowerSubsystem, FruDevices, telemetry
    metric reports, UpdateService, FirmwareInventory, and Systems. SMC coverage is
    ComputerSystem, Memory, Processors, and FirmwareInventory. Every area is enabled
    unless collection_args.enabled turns it off.
    Collection follows links the service publishes and does not apply product member expectations.

    Keep these outside node-scraper core: IPMI, SSH commands and file capture, PLDM,
    manufacturing-tool access, vendor-only BMC actions, BIOS and diagnostic logs, CPLD,
    post codes, SOL, CPER, and product checks for chassis topology, ports, PCIe, sensors,
    certificates, and firmware integrity. Non-Redfish fallbacks stay with the product
    collector that owns them.
    """

    DATA_MODEL = RedfishInventoryDataModel
    COLLECTOR = RedfishInventoryCollector
    COLLECTOR_ARGS = RedfishInventoryCollectorArgs


class AmcRedfishInventoryPlugin(RedfishInventoryPlugin):
    """Collect the same Redfish inventory through the BMC SSH proxy.

    Pair this with RedfishInventoryPlugin so one run reads the BMC on the direct
    Redfish connection and the AMC on RedfishSshProxyConnectionManager. collection_args
    are the same for both plugins.
    """

    CONNECTION_TYPE = RedfishSshProxyConnectionManager  # type: ignore[assignment]
