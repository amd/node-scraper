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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.network.network_collector import NetworkCollector
from nodescraper.plugins.inband.network.networkdata import (
    BroadcomNicDevice,
    BroadcomNicQos,
    EthtoolInfo,
    IpAddress,
    Neighbor,
    NetworkDataModel,
    NetworkInterface,
    Route,
    RoutingRule,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return NetworkCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


# Sample command outputs for testing (mock data)
IP_ADDR_OUTPUT = """1: lo: <LOOPBACK,UP,LOWER_UP> mtu 12345 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 5678 qdisc mq state UP group default qlen 1000
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
    inet 1.123.123.100/24 brd 1.123.123.255 scope global noprefixroute eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::aabb:ccff/64 scope link
       valid_lft forever preferred_lft forever"""

IP_ROUTE_OUTPUT = """default via 2.123.123.1 dev eth0 proto static metric 100
2.123.123.0/24 dev eth0 proto kernel scope link src 2.123.123.100 metric 100
7.8.0.0/16 dev docker0 proto kernel scope link src 7.8.0.1 linkdown"""

IP_RULE_OUTPUT = """0:	from all lookup local
89145:	from all lookup main
56789:	from all lookup default"""

IP_NEIGHBOR_OUTPUT = """50.50.1.50 dev eth0 lladdr 11:22:33:44:55:66 STALE
50.50.1.1 dev eth0 lladdr 99:88:77:66:55:44 REACHABLE"""

ETHTOOL_OUTPUT = """Settings for ethmock123:
	Supported ports: [ TP ]
	Supported link modes:   10mockbaseT/Half
				123mockbaseT/Half
				1234mockbaseT/Full
	Supported pause frame use: Symmetric
	Supports auto-negotiation: Yes
	Supported FEC modes: Not reported
	Advertised link modes:  10mockbaseT/Half 10mockbaseT/Full
				167mockbaseT/Half 167mockbaseT/Full
				1345mockbaseT/Full
	Advertised pause frame use: Symmetric
	Advertised auto-negotiation: Yes
	Advertised FEC modes: Xyz ABCfec
	Speed: 1000mockMb/s
	Duplex: Full
	Port: MockedTwisted Pair
	PHYAD: 1
	Transceiver: internal
	Auto-negotiation: on
	MDI-X: on (auto)
	Supports Wake-on: qwerty
	Wake-on: g
	Current message level: 0x123123
	Link detected: yes"""

ETHTOOL_NO_LINK_OUTPUT = """Settings for ethmock1:
	Supported ports: [ FIBRE ]
	Supported link modes:   11122mockbaseT/Full
	Speed: Unknown!
	Duplex: Unknown!
	Port: FIBRE
	Auto-negotiation: off
	Link detected: no"""


def test_parse_ip_addr_loopback(collector):
    """Test parsing loopback interface from ip addr output"""
    interfaces = collector._parse_ip_addr(IP_ADDR_OUTPUT)

    # Find loopback interface
    lo = next((i for i in interfaces if i.name == "lo"), None)
    assert lo is not None
    assert lo.index == 1
    assert lo.state == "UNKNOWN"
    assert lo.mtu == 12345
    assert lo.qdisc == "noqueue"
    assert lo.mac_address == "00:00:00:00:00:00"
    assert "LOOPBACK" in lo.flags
    assert "UP" in lo.flags

    # Check addresses
    assert len(lo.addresses) == 2
    ipv4 = next((a for a in lo.addresses if a.family == "inet"), None)
    assert ipv4 is not None
    assert ipv4.address == "127.0.0.1"
    assert ipv4.prefix_len == 8
    assert ipv4.scope == "host"


def test_parse_ip_addr_ethernet(collector):
    """Test parsing ethernet interface from ip addr output"""
    interfaces = collector._parse_ip_addr(IP_ADDR_OUTPUT)

    # Find ethernet interface
    eth = next((i for i in interfaces if i.name == "eth0"), None)
    assert eth is not None
    assert eth.index == 2
    assert eth.state == "UP"
    assert eth.mtu == 5678
    assert eth.qdisc == "mq"
    assert eth.mac_address == "aa:bb:cc:dd:ee:ff"
    assert "BROADCAST" in eth.flags
    assert "MULTICAST" in eth.flags

    # Check IPv4 address
    ipv4 = next((a for a in eth.addresses if a.family == "inet"), None)
    assert ipv4 is not None
    assert ipv4.address == "1.123.123.100"
    assert ipv4.prefix_len == 24
    assert ipv4.broadcast == "1.123.123.255"
    assert ipv4.scope == "global"


def test_parse_ip_route_default(collector):
    """Test parsing default route"""
    routes = collector._parse_ip_route(IP_ROUTE_OUTPUT)

    # Find default route
    default_route = next((r for r in routes if r.destination == "default"), None)
    assert default_route is not None
    assert default_route.gateway == "2.123.123.1"
    assert default_route.device == "eth0"
    assert default_route.protocol == "static"
    assert default_route.metric == 100


def test_parse_ip_route_network(collector):
    """Test parsing network route with source"""
    routes = collector._parse_ip_route(IP_ROUTE_OUTPUT)

    # Find network route
    net_route = next((r for r in routes if r.destination == "2.123.123.0/24"), None)
    assert net_route is not None
    assert net_route.gateway is None  # Direct route, no gateway
    assert net_route.device == "eth0"
    assert net_route.protocol == "kernel"
    assert net_route.scope == "link"
    assert net_route.source == "2.123.123.100"
    assert net_route.metric == 100


def test_parse_ip_route_docker(collector):
    """Test parsing docker bridge route"""
    routes = collector._parse_ip_route(IP_ROUTE_OUTPUT)

    # Find docker route
    docker_route = next((r for r in routes if r.destination == "7.8.0.0/16"), None)
    assert docker_route is not None
    assert docker_route.gateway is None
    assert docker_route.device == "docker0"
    assert docker_route.protocol == "kernel"
    assert docker_route.scope == "link"
    assert docker_route.source == "7.8.0.1"


def test_parse_ip_rule_basic(collector):
    """Test parsing routing rules"""
    rules = collector._parse_ip_rule(IP_RULE_OUTPUT)

    assert len(rules) == 3

    # Check local rule
    local_rule = next((r for r in rules if r.priority == 0), None)
    assert local_rule is not None
    assert local_rule.source is None  # "from all"
    assert local_rule.destination is None
    assert local_rule.table == "local"
    assert local_rule.action == "lookup"

    # Check main rule
    main_rule = next((r for r in rules if r.priority == 89145), None)
    assert main_rule is not None
    assert main_rule.table == "main"

    # Check default rule
    default_rule = next((r for r in rules if r.priority == 56789), None)
    assert default_rule is not None
    assert default_rule.table == "default"


def test_parse_ip_rule_complex(collector):
    """Test parsing complex routing rule with all fields"""
    complex_rule_output = (
        "100: from 192.168.1.0/24 to 10.0.0.0/8 iif eth0 oif eth1 fwmark 0x10 lookup custom_table"
    )

    rules = collector._parse_ip_rule(complex_rule_output)

    assert len(rules) == 1
    rule = rules[0]
    assert rule.priority == 100
    assert rule.source == "192.168.1.0/24"
    assert rule.destination == "10.0.0.0/8"
    assert rule.iif == "eth0"
    assert rule.oif == "eth1"
    assert rule.fwmark == "0x10"
    assert rule.table == "custom_table"
    assert rule.action == "lookup"


def test_parse_ip_neighbor_reachable(collector):
    """Test parsing neighbor entries"""
    neighbors = collector._parse_ip_neighbor(IP_NEIGHBOR_OUTPUT)

    # Check REACHABLE neighbor
    reachable = next((n for n in neighbors if n.state == "REACHABLE"), None)
    assert reachable is not None
    assert reachable.ip_address == "50.50.1.1"
    assert reachable.device == "eth0"
    assert reachable.mac_address == "99:88:77:66:55:44"
    assert reachable.state == "REACHABLE"


def test_parse_ip_neighbor_stale(collector):
    """Test parsing STALE neighbor entry"""
    neighbors = collector._parse_ip_neighbor(IP_NEIGHBOR_OUTPUT)

    # Check STALE neighbor
    stale = next((n for n in neighbors if n.state == "STALE"), None)
    assert stale is not None
    assert stale.ip_address == "50.50.1.50"
    assert stale.device == "eth0"
    assert stale.mac_address == "11:22:33:44:55:66"
    assert stale.state == "STALE"


def test_parse_ip_neighbor_with_flags(collector):
    """Test parsing neighbor with flags"""
    neighbor_with_flags = "10.0.0.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE router proxy"

    neighbors = collector._parse_ip_neighbor(neighbor_with_flags)

    assert len(neighbors) == 1
    neighbor = neighbors[0]
    assert neighbor.ip_address == "10.0.0.1"
    assert neighbor.mac_address == "aa:bb:cc:dd:ee:ff"
    assert neighbor.state == "REACHABLE"
    assert "router" in neighbor.flags
    assert "proxy" in neighbor.flags


def test_collect_data_success(collector, conn_mock):
    """Test successful collection of all network data"""
    collector.system_info.os_family = OSFamily.LINUX

    # Mock successful command execution
    def run_sut_cmd_side_effect(cmd, **kwargs):
        if "addr show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ADDR_OUTPUT, command=cmd)
        elif "route show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ROUTE_OUTPUT, command=cmd)
        elif "rule show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_RULE_OUTPUT, command=cmd)
        elif "neighbor show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_NEIGHBOR_OUTPUT, command=cmd)
        elif "ethtool" in cmd:
            # Fail ethtool commands (simulating no sudo or not supported)
            return MagicMock(exit_code=1, stdout="", command=cmd)
        return MagicMock(exit_code=1, stdout="", command=cmd)

    collector._run_sut_cmd = MagicMock(side_effect=run_sut_cmd_side_effect)

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert isinstance(data, NetworkDataModel)
    assert len(data.interfaces) == 2
    assert len(data.routes) == 3
    assert len(data.rules) == 3
    assert len(data.neighbors) == 2
    assert "2 interfaces" in result.message
    assert "3 routes" in result.message
    assert "3 rules" in result.message
    assert "2 neighbors" in result.message
    assert "ethtool" in result.message


def test_collect_data_addr_failure(collector, conn_mock):
    """Test collection when ip addr command fails"""
    collector.system_info.os_family = OSFamily.LINUX

    # Mock failed addr command but successful others
    def run_sut_cmd_side_effect(cmd, **kwargs):
        if "addr show" in cmd:
            return MagicMock(exit_code=1, command=cmd)
        elif "route show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ROUTE_OUTPUT, command=cmd)
        elif "rule show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_RULE_OUTPUT, command=cmd)
        elif "neighbor show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_NEIGHBOR_OUTPUT, command=cmd)
        elif "ethtool" in cmd:
            return MagicMock(exit_code=1, command=cmd)
        elif "lldpcli" in cmd or "lldpctl" in cmd:
            # LLDP commands fail (not available)
            return MagicMock(exit_code=1, command=cmd)
        elif "niccli" in cmd:
            # Broadcom NIC commands fail (not available)
            return MagicMock(exit_code=1, command=cmd)
        elif "nicctl" in cmd:
            # Pensando NIC commands fail (not available)
            return MagicMock(exit_code=1, command=cmd)
        return MagicMock(exit_code=1, command=cmd)

    collector._run_sut_cmd = MagicMock(side_effect=run_sut_cmd_side_effect)

    result, data = collector.collect_data()

    # Should still return data from successful commands
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.interfaces) == 0  # Failed
    assert len(data.routes) == 3  # Success
    assert len(data.rules) == 3  # Success
    assert len(data.neighbors) == 2  # Success
    assert len(data.ethtool_info) == 0  # No interfaces, so no ethtool data
    assert len(result.events) > 0


def test_collect_data_all_failures(collector, conn_mock):
    """Test collection when all commands fail"""
    collector.system_info.os_family = OSFamily.LINUX

    # Mock all commands failing (including ethtool, LLDP, Broadcom, Pensando)
    def run_sut_cmd_side_effect(cmd, **kwargs):
        return MagicMock(exit_code=1, command=cmd)

    collector._run_sut_cmd = MagicMock(side_effect=run_sut_cmd_side_effect)

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert len(result.events) > 0


def test_parse_empty_output(collector):
    """Test parsing empty command output"""
    interfaces = collector._parse_ip_addr("")
    routes = collector._parse_ip_route("")
    rules = collector._parse_ip_rule("")
    neighbors = collector._parse_ip_neighbor("")

    assert len(interfaces) == 0
    assert len(routes) == 0
    assert len(rules) == 0
    assert len(neighbors) == 0


def test_parse_malformed_output(collector):
    """Test parsing malformed output gracefully"""
    malformed = "this is not valid ip output\nsome random text\n123 456"

    # Should not crash, just return empty or skip bad lines
    interfaces = collector._parse_ip_addr(malformed)
    routes = collector._parse_ip_route(malformed)
    neighbors = collector._parse_ip_neighbor(malformed)

    # Parser should handle gracefully
    assert isinstance(interfaces, list)
    assert isinstance(routes, list)
    assert isinstance(neighbors, list)


def test_parse_ip_addr_ipv6_only(collector):
    """Test parsing interface with only IPv6 address"""
    ipv6_only = """3: eth1: <BROADCAST,MULTICAST,UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
    inet6 fe80::a8bb:ccff:fedd:eeff/64 scope link
       valid_lft forever preferred_lft forever"""

    interfaces = collector._parse_ip_addr(ipv6_only)

    assert len(interfaces) == 1
    eth1 = interfaces[0]
    assert eth1.name == "eth1"
    assert len(eth1.addresses) == 1
    assert eth1.addresses[0].family == "inet6"
    assert eth1.addresses[0].address == "fe80::a8bb:ccff:fedd:eeff"
    assert eth1.addresses[0].prefix_len == 64


def test_parse_ip_rule_with_action(collector):
    """Test parsing rule with unreachable action"""
    rule_with_action = "200: from 10.0.0.5 unreachable"

    rules = collector._parse_ip_rule(rule_with_action)

    assert len(rules) == 1
    rule = rules[0]
    assert rule.priority == 200
    assert rule.source == "10.0.0.5"
    assert rule.action == "unreachable"
    assert rule.table is None


def test_parse_ethtool_basic(collector):
    """Test parsing basic ethtool output"""
    ethtool_info = collector._parse_ethtool("ethmock123", ETHTOOL_OUTPUT)

    assert ethtool_info.interface == "ethmock123"
    assert ethtool_info.speed == "1000mockMb/s"
    assert ethtool_info.duplex == "Full"
    assert ethtool_info.port == "MockedTwisted Pair"
    assert ethtool_info.auto_negotiation == "on"
    assert ethtool_info.link_detected == "yes"
    assert "Speed" in ethtool_info.settings
    assert ethtool_info.settings["Speed"] == "1000mockMb/s"
    assert ethtool_info.settings["PHYAD"] == "1"
    assert ethtool_info.raw_output == ETHTOOL_OUTPUT


def test_parse_ethtool_supported_link_modes(collector):
    """Test parsing supported link modes from ethtool output"""
    ethtool_info = collector._parse_ethtool("ethmock123", ETHTOOL_OUTPUT)

    # Check supported link modes are stored in settings dict
    # Note: The current implementation stores link modes in settings dict,
    # not in the supported_link_modes list
    assert "Supported link modes" in ethtool_info.settings
    assert "10mockbaseT/Half" in ethtool_info.settings["Supported link modes"]


def test_parse_ethtool_advertised_link_modes(collector):
    """Test parsing advertised link modes from ethtool output"""
    ethtool_info = collector._parse_ethtool("ethmock123", ETHTOOL_OUTPUT)

    # Check advertised link modes are stored in settings dict
    # Note: The current implementation stores link modes in settings dict,
    # not in the advertised_link_modes list
    assert "Advertised link modes" in ethtool_info.settings
    assert "10mockbaseT/Half" in ethtool_info.settings["Advertised link modes"]
    assert "10mockbaseT/Full" in ethtool_info.settings["Advertised link modes"]


def test_parse_ethtool_no_link(collector):
    """Test parsing ethtool output when link is down"""
    ethtool_info = collector._parse_ethtool("ethmock1", ETHTOOL_NO_LINK_OUTPUT)

    assert ethtool_info.interface == "ethmock1"
    assert ethtool_info.speed == "Unknown!"
    assert ethtool_info.duplex == "Unknown!"
    assert ethtool_info.port == "FIBRE"
    assert ethtool_info.auto_negotiation == "off"
    assert ethtool_info.link_detected == "no"
    # Check supported link modes are stored in settings dict
    assert "Supported link modes" in ethtool_info.settings
    assert "11122mockbaseT/Full" in ethtool_info.settings["Supported link modes"]


def test_parse_ethtool_empty_output(collector):
    """Test parsing empty ethtool output"""
    ethtool_info = collector._parse_ethtool("eth0", "")

    assert ethtool_info.interface == "eth0"
    assert ethtool_info.speed is None
    assert ethtool_info.duplex is None
    assert ethtool_info.link_detected is None
    assert len(ethtool_info.settings) == 0
    assert len(ethtool_info.supported_link_modes) == 0
    assert len(ethtool_info.advertised_link_modes) == 0


def test_network_data_model_creation(collector):
    """Test creating NetworkDataModel with all components"""
    interface = NetworkInterface(
        name="ethmock123",
        index=1,
        state="UP",
        mtu=5678,
        addresses=[IpAddress(address="1.123.123.100", prefix_len=24, family="inet")],
    )

    route = Route(destination="default", gateway="2.123.123.1", device="ethmock123")

    rule = RoutingRule(priority=100, source="1.123.123.0/24", table="main")

    neighbor = Neighbor(
        ip_address="50.50.1.1",
        device="ethmock123",
        mac_address="11:22:33:44:55:66",
        state="REACHABLE",
    )

    ethtool_info = EthtoolInfo(
        interface="ethmock123", raw_output=ETHTOOL_OUTPUT, speed="1000mockMb/s", duplex="Full"
    )

    data = NetworkDataModel(
        interfaces=[interface],
        routes=[route],
        rules=[rule],
        neighbors=[neighbor],
        ethtool_info={"ethmock123": ethtool_info},
    )

    assert len(data.interfaces) == 1
    assert len(data.routes) == 1
    assert len(data.rules) == 1
    assert len(data.neighbors) == 1
    assert len(data.ethtool_info) == 1
    assert data.interfaces[0].name == "ethmock123"
    assert data.ethtool_info["ethmock123"].speed == "1000mockMb/s"


# Sample Broadcom NIC command outputs for testing
NICCLI_LISTDEV_OUTPUT = """root@smci355-ccs-aus-n13-25:/# niccli --list_devices

1 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#1 Port#1)
     Device Interface Name     : benic1p1
     MAC Address               : 8C:84:74:37:C3:70
     PCI Address               : 0000:06:00.0

2 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#2 Port#1)
     Device Interface Name     : benic2p1
     MAC Address               : 8C:84:74:37:DB:D0
     PCI Address               : 0000:16:00.0

3 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#3 Port#1)
     Device Interface Name     : benic4p1
     MAC Address               : 8C:84:74:37:6C:10
     PCI Address               : 0000:66:00.0

4 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#4 Port#1)
     Device Interface Name     : benic3p1
     MAC Address               : 8C:84:74:37:BB:F0
     PCI Address               : 0000:76:00.0

5 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#5 Port#1)
     Device Interface Name     : benic5p1
     MAC Address               : 8C:84:74:37:8E:A0
     PCI Address               : 0000:86:00.0

6 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#6 Port#1)
     Device Interface Name     : benic6p1
     MAC Address               : 6C:92:CF:9A:15:10
     PCI Address               : 0000:96:00.0

7 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#7 Port#1)
     Device Interface Name     : benic8p1
     MAC Address               : 8C:84:74:37:69:90
     PCI Address               : 0000:E6:00.0

8 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#8 Port#1)
     Device Interface Name     : benic7p1
     MAC Address               : 8C:84:74:37:C1:40
     PCI Address               : 0000:F6:00.0
"""

NICCLI_QOS_OUTPUT = """root@smci355-ccs-aus-n13-25:/# niccli --dev 1 qos --ets --show

IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0 1:0 2:0 3:1 4:0 5:0 6:0 7:2
         TC Bandwidth: 50% 50% 0%
         TSA_MAP: 0:ets 1:ets 2:strict
IEEE 8021QAZ PFC TLV:
         PFC enabled: 3
IEEE 8021QAZ APP TLV:
         APP#0:
          Priority: 7
          Sel: 5
          DSCP: 48

         APP#1:
          Priority: 3
          Sel: 5
          DSCP: 26

         APP#2:
          Priority: 3
          Sel: 3
          UDP or DCCP: 4791

TC Rate Limit: 100% 100% 100% 0% 0% 0% 0% 0%
"""

NICCLI_LISTDEV_SINGLE_DEVICE = """1 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#1 Port#1)
     Device Interface Name     : benic1p1
     MAC Address               : 8C:84:74:37:C3:70
     PCI Address               : 0000:06:00.0
"""

NICCLI_QOS_MINIMAL_OUTPUT = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0 1:1
         TC Bandwidth: 50% 50%
         TSA_MAP: 0:ets 1:strict
IEEE 8021QAZ PFC TLV:
         PFC enabled: 1
TC Rate Limit: 100% 100%
"""


def test_parse_niccli_listdev_multiple_devices(collector):
    """Test parsing multiple Broadcom NIC devices from niccli --list_devices output"""
    devices = collector._parse_niccli_listdev(NICCLI_LISTDEV_OUTPUT)

    assert len(devices) == 8

    # Check first device
    device1 = devices[0]
    assert device1.device_num == 1
    assert device1.model == "Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC"
    assert device1.adapter_port == "Adp#1 Port#1"
    assert device1.interface_name == "benic1p1"
    assert device1.mac_address == "8C:84:74:37:C3:70"
    assert device1.pci_address == "0000:06:00.0"

    # Check another device (device 3)
    device3 = devices[2]
    assert device3.device_num == 3
    assert device3.interface_name == "benic4p1"
    assert device3.mac_address == "8C:84:74:37:6C:10"
    assert device3.pci_address == "0000:66:00.0"

    # Check last device
    device8 = devices[7]
    assert device8.device_num == 8
    assert device8.interface_name == "benic7p1"
    assert device8.mac_address == "8C:84:74:37:C1:40"
    assert device8.pci_address == "0000:F6:00.0"


def test_parse_niccli_listdev_single_device(collector):
    """Test parsing single Broadcom NIC device"""
    devices = collector._parse_niccli_listdev(NICCLI_LISTDEV_SINGLE_DEVICE)

    assert len(devices) == 1
    device = devices[0]
    assert device.device_num == 1
    assert device.model == "Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC"
    assert device.adapter_port == "Adp#1 Port#1"
    assert device.interface_name == "benic1p1"
    assert device.mac_address == "8C:84:74:37:C3:70"
    assert device.pci_address == "0000:06:00.0"


def test_parse_niccli_listdev_empty_output(collector):
    """Test parsing empty niccli --list_devices output"""
    devices = collector._parse_niccli_listdev("")

    assert len(devices) == 0


def test_parse_niccli_listdev_malformed_output(collector):
    """Test parsing malformed niccli --list_devices output gracefully"""
    malformed = """some random text
not a valid device line
123 invalid format
"""

    devices = collector._parse_niccli_listdev(malformed)

    # Should handle gracefully, return empty list or skip invalid lines
    assert isinstance(devices, list)


def test_parse_niccli_qos_complete(collector):
    """Test parsing complete Broadcom NIC QoS output with all fields"""
    qos = collector._parse_niccli_qos(1, NICCLI_QOS_OUTPUT)

    assert qos.device_num == 1
    assert qos.raw_output == NICCLI_QOS_OUTPUT

    # Check PRIO_MAP
    assert len(qos.prio_map) == 8
    assert qos.prio_map[0] == 0
    assert qos.prio_map[1] == 0
    assert qos.prio_map[3] == 1
    assert qos.prio_map[7] == 2

    # Check TC Bandwidth
    assert len(qos.tc_bandwidth) == 3
    assert qos.tc_bandwidth[0] == 50
    assert qos.tc_bandwidth[1] == 50
    assert qos.tc_bandwidth[2] == 0

    # Check TSA_MAP
    assert len(qos.tsa_map) == 3
    assert qos.tsa_map[0] == "ets"
    assert qos.tsa_map[1] == "ets"
    assert qos.tsa_map[2] == "strict"

    # Check PFC enabled
    assert qos.pfc_enabled == 3

    # Check APP entries
    assert len(qos.app_entries) == 3

    # Check APP#0
    app0 = qos.app_entries[0]
    assert app0.priority == 7
    assert app0.sel == 5
    assert app0.dscp == 48
    assert app0.protocol is None
    assert app0.port is None

    # Check APP#1
    app1 = qos.app_entries[1]
    assert app1.priority == 3
    assert app1.sel == 5
    assert app1.dscp == 26

    # Check APP#2 (with protocol and port)
    app2 = qos.app_entries[2]
    assert app2.priority == 3
    assert app2.sel == 3
    assert app2.dscp is None
    assert app2.protocol == "UDP or DCCP"
    assert app2.port == 4791

    # Check TC Rate Limit
    assert len(qos.tc_rate_limit) == 8
    assert qos.tc_rate_limit[0] == 100
    assert qos.tc_rate_limit[1] == 100
    assert qos.tc_rate_limit[2] == 100
    assert qos.tc_rate_limit[3] == 0
    assert qos.tc_rate_limit[7] == 0


def test_parse_niccli_qos_minimal(collector):
    """Test parsing minimal Broadcom NIC QoS output"""
    qos = collector._parse_niccli_qos(2, NICCLI_QOS_MINIMAL_OUTPUT)

    assert qos.device_num == 2
    assert qos.raw_output == NICCLI_QOS_MINIMAL_OUTPUT

    # Check PRIO_MAP
    assert len(qos.prio_map) == 2
    assert qos.prio_map[0] == 0
    assert qos.prio_map[1] == 1

    # Check TC Bandwidth
    assert len(qos.tc_bandwidth) == 2
    assert qos.tc_bandwidth[0] == 50
    assert qos.tc_bandwidth[1] == 50

    # Check TSA_MAP
    assert len(qos.tsa_map) == 2
    assert qos.tsa_map[0] == "ets"
    assert qos.tsa_map[1] == "strict"

    # Check PFC enabled
    assert qos.pfc_enabled == 1

    # Check APP entries (should be empty)
    assert len(qos.app_entries) == 0

    # Check TC Rate Limit
    assert len(qos.tc_rate_limit) == 2
    assert qos.tc_rate_limit[0] == 100
    assert qos.tc_rate_limit[1] == 100


def test_parse_niccli_qos_empty_output(collector):
    """Test parsing empty QoS output"""
    qos = collector._parse_niccli_qos(1, "")

    assert qos.device_num == 1
    assert qos.raw_output == ""
    assert len(qos.prio_map) == 0
    assert len(qos.tc_bandwidth) == 0
    assert len(qos.tsa_map) == 0
    assert qos.pfc_enabled is None
    assert len(qos.app_entries) == 0
    assert len(qos.tc_rate_limit) == 0


def test_parse_niccli_qos_no_app_entries(collector):
    """Test parsing QoS output without APP entries"""
    qos_no_app = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0 1:1 2:2
         TC Bandwidth: 33% 33% 34%
         TSA_MAP: 0:ets 1:ets 2:ets
IEEE 8021QAZ PFC TLV:
         PFC enabled: 7
TC Rate Limit: 100% 100% 100%
"""

    qos = collector._parse_niccli_qos(5, qos_no_app)

    assert qos.device_num == 5
    assert len(qos.prio_map) == 3
    assert len(qos.tc_bandwidth) == 3
    assert len(qos.tsa_map) == 3
    assert qos.pfc_enabled == 7
    assert len(qos.app_entries) == 0
    assert len(qos.tc_rate_limit) == 3


def test_parse_niccli_qos_multiple_app_protocols(collector):
    """Test parsing QoS with APP entries having different protocols"""
    qos_multi_protocol = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0
         TC Bandwidth: 100%
         TSA_MAP: 0:ets
IEEE 8021QAZ PFC TLV:
         PFC enabled: 0
IEEE 8021QAZ APP TLV:
         APP#0:
          Priority: 5
          Sel: 3
          TCP: 8080

         APP#1:
          Priority: 6
          Sel: 3
          UDP: 9000

TC Rate Limit: 100%
"""

    qos = collector._parse_niccli_qos(3, qos_multi_protocol)

    assert len(qos.app_entries) == 2

    # Check TCP entry
    app0 = qos.app_entries[0]
    assert app0.priority == 5
    assert app0.sel == 3
    assert app0.protocol == "TCP"
    assert app0.port == 8080

    # Check UDP entry
    app1 = qos.app_entries[1]
    assert app1.priority == 6
    assert app1.sel == 3
    assert app1.protocol == "UDP"
    assert app1.port == 9000


def test_parse_niccli_qos_malformed_values(collector):
    """Test parsing QoS output with malformed values gracefully"""
    malformed = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:invalid 1:1 bad:data
         TC Bandwidth: 50% invalid 50%
         TSA_MAP: 0:ets bad:value 1:strict
IEEE 8021QAZ PFC TLV:
         PFC enabled: not_a_number
TC Rate Limit: 100% bad% 100%
"""

    qos = collector._parse_niccli_qos(1, malformed)

    # Should skip invalid entries but parse valid ones
    assert qos.device_num == 1
    # Should have parsed valid prio_map entry (1:1)
    assert 1 in qos.prio_map
    assert qos.prio_map[1] == 1
    # Should have parsed valid bandwidth entries
    assert 50 in qos.tc_bandwidth
    # Should have parsed valid tsa_map entries
    assert qos.tsa_map.get(0) == "ets"
    assert qos.tsa_map.get(1) == "strict"
    # PFC should be None due to invalid number
    assert qos.pfc_enabled is None


def test_network_data_model_with_broadcom_nic(collector):
    """Test creating NetworkDataModel with Broadcom NIC data"""
    device = BroadcomNicDevice(
        device_num=1,
        model="Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC",
        adapter_port="Adp#1 Port#1",
        interface_name="benic1p1",
        mac_address="8C:84:74:37:C3:70",
        pci_address="0000:06:00.0",
    )

    qos = BroadcomNicQos(
        device_num=1,
        raw_output="test output",
        prio_map={0: 0, 1: 1},
        tc_bandwidth=[50, 50],
        tsa_map={0: "ets", 1: "strict"},
        pfc_enabled=3,
        tc_rate_limit=[100, 100],
    )

    data = NetworkDataModel(
        interfaces=[],
        routes=[],
        rules=[],
        neighbors=[],
        ethtool_info={},
        broadcom_nic_devices=[device],
        broadcom_nic_qos={1: qos},
    )

    assert len(data.broadcom_nic_devices) == 1
    assert len(data.broadcom_nic_qos) == 1
    assert data.broadcom_nic_devices[0].device_num == 1
    assert data.broadcom_nic_devices[0].interface_name == "benic1p1"
    assert data.broadcom_nic_qos[1].device_num == 1
    assert data.broadcom_nic_qos[1].pfc_enabled == 3
