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

import pytest

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.fabrics.fabrics_collector import FabricsCollector
from nodescraper.plugins.inband.fabrics.fabricsdata import (
    FabricsDataModel,
    IbdevNetdevMapping,
    IbstatDevice,
    IbvDeviceInfo,
    MstDevice,
    MstStatus,
    OfedInfo,
    RdmaDevice,
    RdmaInfo,
    RdmaLink,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return FabricsCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


# Sample command outputs for testing (mock data)

IBSTAT_OUTPUT = """CA 'mlx5_0'
	CA type: AB5678
	Number of ports: 1
	Firmware version: 10.10.1010
	Hardware version: 0X0
	Node GUID: 0x506b4b0300abcdef
	System image GUID: 0x506b4b0300abcdef
Port 1:
		State: Active
		Physical state: LinkUp
		Rate: 200
		Base lid: 0
		LMC: 0
		SM lid: 0
		Capability mask: 0x2651e848
		Port GUID: 0x506b4b0300abcdef
		Link layer: MockBand"""

IBSTAT_EMPTY_OUTPUT = ""

# ibv_devinfo output
IBV_DEVINFO_OUTPUT = """hca_id:	mlx5_0
	transport:			MockBand (0)
	fw_ver:				20.32.1010
	node_guid:			1234:7891:00ab:cdef
	sys_image_guid:			1234:7891:00ab:cdef
	vendor_id:			0x6789
	vendor_part_id:			4123
	hw_ver:				0x0
	board_id:			MT_0000000010
	phys_port_cnt:			1
		port:	1
			state:			PORT_ACTIVE (4)
			max_mtu:		4096 (5)
			active_mtu:		4096 (5)
			sm_lid:			0
			port_lid:		0
			port_lmc:		0x00
			link_layer:		MockBand"""

# ls -l /sys/class/infiniband/*/device/net output - RoCE devices
IB_DEV_NETDEVS_OUTPUT = """/sys/class/infiniband/rocep105s0/device/net:
total 0
drwxr-xr-x 5 root root 0 Jan  8 18:01 benic5p1

/sys/class/infiniband/rocep121s0/device/net:
total 0
drwxr-xr-x 5 root root 0 Jan  8 18:01 benic6p1
"""

IB_DEV_NETDEVS_EMPTY = ""

# ofed_info output
OFED_INFO_OUTPUT = "OFED-internal-25.11-1.2.3:"

# mst status -v output - new tabular format
MST_STATUS_OUTPUT = """MST modules:
------------
    MST PCI module is not loaded
    MST PCI configuration module loaded

PCI devices:
------------
DEVICE_TYPE             MST                         PCI           RDMA            NET                     NUMA
ConnectX7(rev:0)        /dev/mst/ab1234_pciconf9    0000:ec:00.0  mlx5_4          net-mock235s0np0         1
ConnectX7(rev:0)        /dev/mst/cd5678_pciconf8    0000:d4:00.0  mlx5_6          net-mock211s0np0         1"""

MST_STATUS_EMPTY = ""

# rdma dev output - RoCE devices
RDMA_DEV_OUTPUT = """0: abcdef25s0: node_type ca fw 1.117.1-a-63 node_guid 1234:56ff:890f:1111 sys_image_guid 1234:56ff:890f:1111
1: abcdef105s0: node_type ca fw 1.117.1-a-63 node_guid 2222:81ff:3333:b450 sys_image_guid 2222:81ff:3333:b450"""

RDMA_DEV_EMPTY = ""

# rdma link output - RoCE devices
RDMA_LINK_OUTPUT = """link rocep9s0/1 state DOWN physical_state POLLING netdev benic8p1
link abcdef25s0/1 state DOWN physical_state POLLING netdev mock7p1
"""

RDMA_LINK_EMPTY = ""


def test_parse_ibstat_basic(collector):
    """Test parsing basic ibstat output"""
    devices = collector._parse_ibstat(IBSTAT_OUTPUT)

    assert len(devices) == 1
    device = devices[0]
    assert device.ca_name == "mlx5_0"
    assert device.ca_type == "AB5678"
    assert device.number_of_ports == 1
    assert device.firmware_version == "10.10.1010"
    assert device.hardware_version == "0X0"
    assert device.node_guid == "0x506b4b0300abcdef"
    assert device.system_image_guid == "0x506b4b0300abcdef"


def test_parse_ibstat_port(collector):
    """Test parsing ibstat port information"""
    devices = collector._parse_ibstat(IBSTAT_OUTPUT)

    assert len(devices) == 1
    device = devices[0]
    assert 1 in device.ports
    port_attrs = device.ports[1]
    assert port_attrs["State"] == "Active"
    assert port_attrs["Physical state"] == "LinkUp"
    assert port_attrs["Rate"] == "200"
    assert port_attrs["Link layer"] == "MockBand"


def test_parse_ibstat_empty(collector):
    """Test parsing empty ibstat output"""
    devices = collector._parse_ibstat(IBSTAT_EMPTY_OUTPUT)
    assert len(devices) == 0


def test_parse_ibv_devinfo_basic(collector):
    """Test parsing basic ibv_devinfo output"""
    devices = collector._parse_ibv_devinfo(IBV_DEVINFO_OUTPUT)

    assert len(devices) == 1
    device = devices[0]
    assert device.device == "mlx5_0"
    assert device.transport_type == "MockBand (0)"
    assert device.fw_ver == "20.32.1010"
    assert device.node_guid == "1234:7891:00ab:cdef"
    assert device.sys_image_guid == "1234:7891:00ab:cdef"
    assert device.vendor_id == "0x6789"
    assert device.vendor_part_id == "4123"
    assert device.hw_ver == "0x0"


def test_parse_ibv_devinfo_port(collector):
    """Test parsing ibv_devinfo port information"""
    devices = collector._parse_ibv_devinfo(IBV_DEVINFO_OUTPUT)

    assert len(devices) == 1
    device = devices[0]
    assert 1 in device.ports
    port_attrs = device.ports[1]
    assert port_attrs["state"] == "PORT_ACTIVE (4)"
    assert port_attrs["link_layer"] == "MockBand"


def test_parse_ib_dev_netdevs(collector):
    """Test parsing ls -l /sys/class/infiniband/*/device/net output"""
    mappings = collector._parse_ib_dev_netdevs(IB_DEV_NETDEVS_OUTPUT)

    assert len(mappings) == 2

    # Check first mapping
    mapping1 = next((m for m in mappings if m.ib_device == "rocep105s0"), None)
    assert mapping1 is not None
    assert mapping1.port == 1
    assert mapping1.netdev == "benic5p1"
    assert mapping1.state is None

    # Check second mapping
    mapping2 = next((m for m in mappings if m.ib_device == "rocep121s0"), None)
    assert mapping2 is not None
    assert mapping2.netdev == "benic6p1"


def test_parse_ib_dev_netdevs_empty(collector):
    """Test parsing empty IB device netdev output"""
    mappings = collector._parse_ib_dev_netdevs(IB_DEV_NETDEVS_EMPTY)
    assert len(mappings) == 0


def test_parse_ofed_info(collector):
    """Test parsing ofed_info output"""
    ofed_info = collector._parse_ofed_info(OFED_INFO_OUTPUT)

    assert ofed_info.version == "OFED-internal-25.11-1.2.3"
    assert ofed_info.raw_output == OFED_INFO_OUTPUT


def test_parse_mst_status_tabular(collector):
    """Test parsing mst status -v output in new tabular format"""
    mst_status = collector._parse_mst_status(MST_STATUS_OUTPUT)

    assert mst_status.mst_started is True
    assert len(mst_status.devices) == 2

    # Check first device
    device1 = next((d for d in mst_status.devices if d.device == "/dev/mst/ab1234_pciconf9"), None)
    assert device1 is not None
    assert device1.pci_address == "0000:ec:00.0"
    assert device1.rdma_device == "mlx5_4"
    assert device1.net_device == "mock235s0np0"
    assert device1.attributes["numa_node"] == "1"
    assert device1.attributes["device_type"] == "ConnectX7(rev:0)"

    # Check second device
    device2 = next((d for d in mst_status.devices if d.device == "/dev/mst/cd5678_pciconf8"), None)
    assert device2 is not None
    assert device2.pci_address == "0000:d4:00.0"
    assert device2.rdma_device == "mlx5_6"
    assert device2.net_device == "mock211s0np0"


def test_parse_mst_status_empty(collector):
    """Test parsing empty mst status output"""
    mst_status = collector._parse_mst_status(MST_STATUS_EMPTY)

    assert mst_status.mst_started is False
    assert len(mst_status.devices) == 0


def test_parse_rdma_dev_roce(collector):
    """Test parsing rdma dev output with RoCE devices"""
    devices = collector._parse_rdma_dev(RDMA_DEV_OUTPUT)

    assert len(devices) == 2

    # Check first device
    device1 = devices[0]
    assert device1.device == "abcdef25s0"
    assert device1.node_type == "ca"
    assert device1.attributes["fw_version"] == "1.117.1-a-63"
    assert device1.node_guid == "1234:56ff:890f:1111"
    assert device1.sys_image_guid == "1234:56ff:890f:1111"

    # Check second device
    device2 = devices[1]
    assert device2.device == "abcdef105s0"
    assert device2.node_type == "ca"
    assert device2.node_guid == "2222:81ff:3333:b450"
    assert device2.sys_image_guid == "2222:81ff:3333:b450"


def test_parse_rdma_dev_empty(collector):
    """Test parsing empty rdma dev output"""
    devices = collector._parse_rdma_dev(RDMA_DEV_EMPTY)
    assert len(devices) == 0


def test_parse_rdma_link_roce(collector):
    """Test parsing rdma link output with RoCE devices"""
    links = collector._parse_rdma_link(RDMA_LINK_OUTPUT)

    assert len(links) == 2

    # Check first link
    link1 = next((link for link in links if link.device == "rocep9s0"), None)
    assert link1 is not None
    assert link1.port == 1
    assert link1.state == "DOWN"
    assert link1.physical_state == "POLLING"
    assert link1.netdev == "benic8p1"

    # Check second link
    link2 = next((link for link in links if link.device == "abcdef25s0"), None)
    assert link2 is not None
    assert link2.netdev == "mock7p1"


def test_parse_rdma_link_empty(collector):
    """Test parsing empty rdma link output"""
    links = collector._parse_rdma_link(RDMA_LINK_EMPTY)
    assert len(links) == 0


def test_fabrics_data_model_creation(collector):
    """Test creating FabricsDataModel with all components"""
    ibstat_device = IbstatDevice(
        ca_name="mlx5_0",
        ca_type="AB5678",
        number_of_ports=1,
        firmware_version="10.10.1010",
        node_guid="0x506b4b0300abcdef",
        ports={1: {"State": "Active"}},
        raw_output=IBSTAT_OUTPUT,
    )

    ibv_device = IbvDeviceInfo(
        device="mlx5_0",
        node_guid="1234:7891:00ab:cdef",
        fw_ver="20.32.1010",
        transport_type="MockBand",
        ports={1: {"state": "PORT_ACTIVE"}},
        raw_output=IBV_DEVINFO_OUTPUT,
    )

    mapping = IbdevNetdevMapping(ib_device="rocep105s0", port=1, netdev="benic5p1", state=None)

    ofed_info = OfedInfo(version="OFED-internal-25.11-1.2.3", raw_output=OFED_INFO_OUTPUT)

    mst_device = MstDevice(
        device="/dev/mst/ab1234_pciconf9",
        pci_address="0000:ec:00.0",
        rdma_device="mlx5_4",
        net_device="mock235s0np0",
        attributes={"numa_node": "1", "device_type": "ConnectX7(rev:0)"},
    )
    mst_status = MstStatus(mst_started=True, devices=[mst_device], raw_output=MST_STATUS_OUTPUT)

    rdma_device = RdmaDevice(
        device="abcdef25s0",
        node_type="ca",
        node_guid="1234:56ff:890f:1111",
        attributes={"fw_version": "1.117.1-a-63"},
    )

    rdma_link = RdmaLink(
        device="abcdef25s0",
        port=1,
        state="DOWN",
        physical_state="POLLING",
        netdev="mock7p1",
    )

    rdma_info = RdmaInfo(devices=[rdma_device], links=[rdma_link], raw_output=RDMA_DEV_OUTPUT)

    data = FabricsDataModel(
        ibstat_devices=[ibstat_device],
        ibv_devices=[ibv_device],
        ibdev_netdev_mappings=[mapping],
        ofed_info=ofed_info,
        mst_status=mst_status,
        rdma_info=rdma_info,
    )

    assert len(data.ibstat_devices) == 1
    assert len(data.ibv_devices) == 1
    assert len(data.ibdev_netdev_mappings) == 1
    assert data.ofed_info.version == "OFED-internal-25.11-1.2.3"
    assert len(data.mst_status.devices) == 1
    assert len(data.rdma_info.devices) == 1
    assert len(data.rdma_info.links) == 1


def test_fabrics_data_model_empty(collector):
    """Test creating empty FabricsDataModel"""
    data = FabricsDataModel(
        ibstat_devices=[],
        ibv_devices=[],
        ibdev_netdev_mappings=[],
        ofed_info=None,
        mst_status=None,
        rdma_info=None,
    )

    assert len(data.ibstat_devices) == 0
    assert len(data.ibv_devices) == 0
    assert len(data.ibdev_netdev_mappings) == 0
    assert data.ofed_info is None
    assert data.mst_status is None
    assert data.rdma_info is None
