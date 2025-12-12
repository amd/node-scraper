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
    def run_sut_cmd_side_effect(cmd):
        if "addr show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ADDR_OUTPUT, command=cmd)
        elif "route show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ROUTE_OUTPUT, command=cmd)
        elif "rule show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_RULE_OUTPUT, command=cmd)
        elif "neighbor show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_NEIGHBOR_OUTPUT, command=cmd)
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


def test_collect_data_addr_failure(collector, conn_mock):
    """Test collection when ip addr command fails"""
    collector.system_info.os_family = OSFamily.LINUX

    # Mock failed addr command but successful others
    def run_sut_cmd_side_effect(cmd):
        if "addr show" in cmd:
            return MagicMock(exit_code=1, stdout="", command=cmd)
        elif "route show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_ROUTE_OUTPUT, command=cmd)
        elif "rule show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_RULE_OUTPUT, command=cmd)
        elif "neighbor show" in cmd:
            return MagicMock(exit_code=0, stdout=IP_NEIGHBOR_OUTPUT, command=cmd)
        return MagicMock(exit_code=1, stdout="", command=cmd)

    collector._run_sut_cmd = MagicMock(side_effect=run_sut_cmd_side_effect)

    result, data = collector.collect_data()

    # Should still return data from successful commands
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.interfaces) == 0  # Failed
    assert len(data.routes) == 3  # Success
    assert len(data.rules) == 3  # Success
    assert len(data.neighbors) == 2  # Success
    assert len(result.events) > 0


def test_collect_data_all_failures(collector, conn_mock):
    """Test collection when all commands fail"""
    collector.system_info.os_family = OSFamily.LINUX

    # Mock all commands failing
    collector._run_sut_cmd = MagicMock(return_value=MagicMock(exit_code=1, stdout="", command="ip"))

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


def test_network_data_model_creation(collector):
    """Test creating NetworkDataModel with all components"""
    interface = NetworkInterface(
        name="eth0",
        index=1,
        state="UP",
        mtu=5678,
        addresses=[IpAddress(address="1.123.123.100", prefix_len=24, family="inet")],
    )

    route = Route(destination="default", gateway="2.123.123.1", device="eth0")

    rule = RoutingRule(priority=100, source="1.123.123.0/24", table="main")

    neighbor = Neighbor(
        ip_address="50.50.1.1", device="eth0", mac_address="11:22:33:44:55:66", state="REACHABLE"
    )

    data = NetworkDataModel(
        interfaces=[interface], routes=[route], rules=[rule], neighbors=[neighbor]
    )

    assert len(data.interfaces) == 1
    assert len(data.routes) == 1
    assert len(data.rules) == 1
    assert len(data.neighbors) == 1
    assert data.interfaces[0].name == "eth0"
