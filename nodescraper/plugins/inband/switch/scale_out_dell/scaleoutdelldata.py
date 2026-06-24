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

from typing import ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from nodescraper.models import DataModel


class DellArpEntry(BaseModel):
    """Single entry from ``show ip arp``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    address: Optional[str] = None
    hardware_address: Optional[str] = None
    interface: Optional[str] = None
    egress_interface: Optional[str] = None
    type: Optional[str] = None
    action: Optional[str] = None

    error_fields: ClassVar[dict[str, str]] = {
        "address": "NOT_NULL",
        "hardware_address": "NOT_NULL",
    }


class DellRouteEntry(BaseModel):
    """Single entry from ``show ip route``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    code: Optional[str] = None
    destination: Optional[str] = None
    gateway: Optional[str] = None
    interface: Optional[str] = None
    distance_metric: Optional[str] = None
    last_update: Optional[str] = None

    error_fields: ClassVar[dict[str, str]] = {
        "destination": "NOT_NULL",
    }


class DellInterfaceStatus(BaseModel):
    """Per-port info from ``show interface status``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None
    oper: Optional[str] = None
    reason: Optional[str] = None
    auto_neg: Optional[str] = None
    speed: Optional[int] = None
    mtu: Optional[int] = None
    alternate_name: Optional[str] = None

    error_fields: ClassVar[dict[str, str]] = {
        "oper": "up",
        "speed": "400000",
    }


class DellFecStatus(BaseModel):
    """Per-port FEC status from ``show interface fec status``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    type: Optional[str] = None
    oper: Optional[str] = None
    admin: Optional[str] = None
    if_state: Optional[str] = None


class DellInterfaceCounters(BaseModel):
    """Per-port summary counters from ``show interface counters``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    state: Optional[str] = None
    rx_ok: Optional[int] = None
    rx_err: Optional[int] = None
    rx_drp: Optional[int] = None
    rx_oversize: Optional[int] = None
    tx_ok: Optional[int] = None
    tx_err: Optional[int] = None
    tx_drp: Optional[int] = None
    tx_oversize: Optional[int] = None

    error_fields: ClassVar[dict[str, str]] = {
        "state": "U",
        "rx_err": "0",
        "rx_oversize": "0",
        "tx_err": "0",
        "tx_oversize": "0",
    }

    warning_fields: ClassVar[dict[str, str]] = {
        "rx_drp": "0",
        "tx_drp": "0",
    }


class DellInterfaceDetailCounters(BaseModel):
    """Detailed per-port counters from ``show interface counters Eth<port>``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    packets_received_64_octets: Optional[int] = None
    packets_received_65_127_octets: Optional[int] = None
    packets_received_128_255_octets: Optional[int] = None
    packets_received_256_511_octets: Optional[int] = None
    packets_received_512_1023_octets: Optional[int] = None
    packets_received_1024_1518_octets: Optional[int] = None
    packets_received_1519_2047_octets: Optional[int] = None
    packets_received_2048_4095_octets: Optional[int] = None
    packets_received_4096_9216_octets: Optional[int] = None
    packets_received_9217_16383_octets: Optional[int] = None
    total_packets_received_without_errors: Optional[int] = None
    unicast_packets_received: Optional[int] = None
    multicast_packets_received: Optional[int] = None
    broadcast_packets_received: Optional[int] = None
    jabbers_received: Optional[int] = None
    fragments_received: Optional[int] = None
    undersize_received: Optional[int] = None
    overruns_received: Optional[int] = None
    crc_errors_received: Optional[int] = None

    packets_transmitted_64_octets: Optional[int] = None
    packets_transmitted_65_127_octets: Optional[int] = None
    packets_transmitted_128_255_octets: Optional[int] = None
    packets_transmitted_256_511_octets: Optional[int] = None
    packets_transmitted_512_1023_octets: Optional[int] = None
    packets_transmitted_1024_1518_octets: Optional[int] = None
    packets_transmitted_1519_2047_octets: Optional[int] = None
    packets_transmitted_2048_4095_octets: Optional[int] = None
    packets_transmitted_4096_9216_octets: Optional[int] = None
    packets_transmitted_9217_16383_octets: Optional[int] = None
    total_packets_transmitted_successfully: Optional[int] = None
    unicast_packets_transmitted: Optional[int] = None
    multicast_packets_transmitted: Optional[int] = None
    broadcast_packets_transmitted: Optional[int] = None

    time_since_counters_last_cleared: Optional[str] = None

    error_fields: ClassVar[dict[str, str]] = {
        "packets_received_9217_16383_octets": "0",
        "packets_transmitted_9217_16383_octets": "0",
        "jabbers_received": "0",
        "fragments_received": "0",
        "undersize_received": "0",
        "overruns_received": "0",
        "crc_errors_received": "0",
    }


class DellQueueCounter(BaseModel):
    """Single queue counter entry from ``show queue counters``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    txq: Optional[str] = None
    counter_pkts: Optional[int] = None
    counter_bytes: Optional[int] = None
    rate_pps: Optional[str] = None
    rate_bps: Optional[str] = None
    rate_bits_ps: Optional[str] = None
    drop_pkts: Optional[int] = None
    drop_bytes: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "drop_pkts": "0",
        "drop_bytes": "0",
    }


class DellPfcStatistics(BaseModel):
    """PFC frames per-priority for a single port and direction.

    Populated from
    ``show qos interface Ethernet all priority-flow-control statistics``
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    pfc0: Optional[int] = None
    pfc1: Optional[int] = None
    pfc2: Optional[int] = None
    pfc3: Optional[int] = None
    pfc4: Optional[int] = None
    pfc5: Optional[int] = None
    pfc6: Optional[int] = None
    pfc7: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "pfc0": "0",
        "pfc1": "0",
        "pfc2": "0",
        "pfc3": "0",
        "pfc4": "0",
        "pfc5": "0",
        "pfc6": "0",
        "pfc7": "0",
    }


class DellPfcWatchdogQueueStats(BaseModel):
    """Per-queue PFC watchdog stats for a port"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    queue: Optional[int] = None
    status: Optional[str] = None
    storms_detected: Optional[int] = None
    storms_restored: Optional[int] = None
    transmitted_ok: Optional[int] = None
    transmitted_drop: Optional[int] = None
    received_ok: Optional[int] = None
    received_drop: Optional[int] = None
    tx_last_ok: Optional[int] = None
    tx_last_drop: Optional[int] = None
    rx_last_ok: Optional[int] = None
    rx_last_drop: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "storms_detected": "0",
        "storms_restored": "0",
        "transmitted_ok": "0",
        "transmitted_drop": "0",
        "received_ok": "0",
        "received_drop": "0",
        "tx_last_ok": "0",
        "tx_last_drop": "0",
        "rx_last_ok": "0",
        "rx_last_drop": "0",
    }


class DellPortData(BaseModel):
    """All collected per-port data for a Dell switch"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    interface_status: Optional[DellInterfaceStatus] = None
    interface_counters: Optional[DellInterfaceCounters] = None
    detail_counters: Optional[DellInterfaceDetailCounters] = None
    fec_status: Optional[DellFecStatus] = None
    pfc_rx_statistics: Optional[DellPfcStatistics] = None
    pfc_tx_statistics: Optional[DellPfcStatistics] = None
    pfc_watchdog_statistics: Optional[List[DellPfcWatchdogQueueStats]] = None
    queue_counters: Optional[List[DellQueueCounter]] = None


class ScaleOutDellDataModel(DataModel):
    """Collected output of Dell SONiC switch commands"""

    ip_arp: Optional[List[DellArpEntry]] = None
    ip_route: Optional[List[DellRouteEntry]] = None
    port_list: Optional[List[str]] = None

    port: Optional[Dict[str, DellPortData]] = None
