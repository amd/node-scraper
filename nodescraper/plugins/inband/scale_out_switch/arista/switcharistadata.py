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

from typing import ClassVar, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from nodescraper.models import DataModel


class AristaVersion(BaseModel):
    """Contains the versioning info"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        protected_namespaces=(),
    )

    image_format_version: Optional[str] = None
    uptime: Optional[float] = None
    model_name: Optional[str] = None
    internal_version: Optional[str] = None
    mem_total: Optional[int] = None
    mfg_name: Optional[str] = None
    serial_number: Optional[str] = None
    system_mac_address: Optional[str] = None
    bootup_timestamp: Optional[float] = None
    mem_free: Optional[int] = None
    version: Optional[str] = None
    config_mac_address: Optional[str] = None
    is_intl_version: Optional[bool] = None
    image_optimization: Optional[str] = None
    internal_build_id: Optional[str] = None
    hardware_revision: Optional[str] = None
    hw_mac_address: Optional[str] = None
    architecture: Optional[str] = None


class LldpNeighbor(BaseModel):
    """Contains the LLDP neighbor info for an Arista switch."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    port: Optional[str] = None
    neighbor_device: Optional[str] = None
    neighbor_port: Optional[str] = None
    ttl: Optional[int] = None


class AristaNeighbors(BaseModel):
    """Contains the neighbor info for an Arista switch."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tables_last_change_time: Optional[float] = None
    tables_age_outs: Optional[int] = None
    tables_inserts: Optional[int] = None
    lldp_neighbors: Optional[List[LldpNeighbor]] = None


class FanConfiguration(BaseModel):
    """Contains the fan configuration info for an Arista switch."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    label: Optional[str] = None
    status: Optional[str] = None
    uptime: Optional[float] = None
    max_speed: Optional[int] = None
    last_speed_stable_change_time: Optional[float] = None
    configured_speed: Optional[int] = None
    actual_speed: Optional[int] = None
    speed_hw_override: Optional[bool] = None
    speed_stable: Optional[bool] = None

    error_fields: ClassVar[dict[str, str]] = {
        "status": "ok",
    }


class AristaSystemEnv(BaseModel):
    """Contains the system environment info for an Arista switch."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    system_status: Optional[str] = None
    fans_status: Optional[str] = None
    ambient_temperature: Optional[float] = None
    airflow_direction: Optional[str] = None
    current_zones: Optional[int] = None
    configured_zones: Optional[int] = None
    default_zones: Optional[bool] = None
    num_cooling_zones: Optional[List[int]] = None
    shutdown_on_insufficient_fans: Optional[bool] = None
    override_fan_speed: Optional[int] = None
    min_fan_speed: Optional[int] = None
    cooling_mode: Optional[str] = None

    power_supply_slots: Optional[List[FanConfiguration]] = None
    fan_tray_slots: Optional[List[FanConfiguration]] = None

    error_fields: ClassVar[dict[str, Union[str, bool]]] = {
        "system_status": "coolingOk",
        "fans_status": "fanAlarmOk",
    }


class VlanInformation(BaseModel):
    """Contains the VLAN info for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    vlan_id: Optional[int] = None
    interface_mode: Optional[str] = None
    interface_forwarding_model: Optional[str] = None

    error_fields: ClassVar[dict[str, str]] = {
        "interface_mode": "routed",
        "interface_forwarding_model": "routed",
    }


class AristaPortStatus(BaseModel):
    """Contains the port status info for an Arista switch."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    link_status: Optional[str] = None
    description: Optional[str] = None
    bandwidth: Optional[int] = None
    duplex: Optional[str] = None
    vlan_information: Optional[VlanInformation] = None
    auto_negotiate_active: Optional[bool] = None
    interface_type: Optional[str] = None
    line_protocol_status: Optional[str] = None
    interface_damped: Optional[bool] = None

    error_fields: ClassVar[dict[str, str]] = {
        "link_status": "connected",
        "bandwidth": "400000000000",
        "duplex": "duplexFull",
        "line_protocol_status": "up",
    }


class AristaPhyStatus(BaseModel):
    """Contains the PHY status info for an Arista switch port.

    Key for status flag fields (from 'show interfaces phy' output):
        U = Link up, D = Link down,
        R = RX Fault, T = TX Fault,
        B = High BER, L = No Block Lock,
        A = No XAUI Lane Alignment,
        0123 = No XAUI lane sync in lane N
    """

    phy_state: Optional[str] = None
    state_changes: Optional[int] = None
    reset_count: Optional[int] = None
    pma_pmd: Optional[str] = None
    pcs: Optional[str] = None
    xaui: Optional[str] = None
    link_up: Optional[bool] = None
    rx_fault: Optional[bool] = None
    tx_fault: Optional[bool] = None
    high_ber: Optional[bool] = None
    no_block_lock: Optional[bool] = None
    no_xaui_lane_alignment: Optional[bool] = None
    no_xaui_lane_sync: Optional[List[int]] = None

    error_fields: ClassVar[dict[str, Union[str, bool]]] = {
        "tx_fault": False,
    }


class AristaCountersErrors(BaseModel):
    """Contains the error counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    in_errors: Optional[int] = None
    frame_too_longs: Optional[int] = None
    out_errors: Optional[int] = None
    frame_too_shorts: Optional[int] = None
    fcs_errors: Optional[int] = None
    alignment_errors: Optional[int] = None
    symbol_errors: Optional[int] = None

    error_fields: ClassVar[dict[str, str]] = {
        "in_errors": "0",
        "frame_too_longs": "0",
        "out_errors": "0",
        "frame_too_shorts": "0",
        "fcs_errors": "0",
        "alignment_errors": "0",
        "symbol_errors": "0",
    }


class AristaPacketCounters(BaseModel):
    """Contains the packet counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    out_broadcast_pkts: Optional[int] = None
    out_ucast_pkts: Optional[int] = None
    in_multicast_pkts: Optional[int] = None
    last_update_timestamp: Optional[float] = None
    in_broadcast_pkts: Optional[int] = None
    in_octets: Optional[int] = None
    out_discards: Optional[int] = None
    out_octets: Optional[int] = None
    in_ucast_pkts: Optional[int] = None
    out_multicast_pkts: Optional[int] = None
    in_discards: Optional[int] = None


class AristaIpCounters(BaseModel):
    """Contains the IP counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ipv4_out_pkts: Optional[int] = None
    ipv4_in_pkts: Optional[int] = None
    ipv6_in_pkts: Optional[int] = None
    ipv6_out_pkts: Optional[int] = None


class AristaBinsCounters(BaseModel):
    """Contains the bins counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    frames_128_to_255_octet: Optional[int] = None
    frames_64_octet: Optional[int] = None
    frames_256_to_511_octet: Optional[int] = None
    frames_1024_to_1522_octet: Optional[int] = None
    frames_512_to_1023_octet: Optional[int] = None
    frames_65_to_127_octet: Optional[int] = None
    frames_1523_to_max_octet: Optional[int] = None


class AristaRatesCounters(BaseModel):
    """Contains the rates counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    out_pps_rate: Optional[float] = None
    in_pps_rate: Optional[float] = None
    description: Optional[str] = None
    last_update_timestamp: Optional[float] = None
    in_pkts_rate: Optional[float] = None
    in_bps_rate: Optional[float] = None
    interval: Optional[int] = None
    out_bps_rate: Optional[float] = None
    out_pkts_rate: Optional[float] = None


class AristaDroppedPacketCounters(BaseModel):
    """Contains the dropped packet counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    in_dropped_pkts: Optional[int] = None
    out_uc_dropped_pkts: Optional[int] = None
    out_mc_dropped_pkts: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "in_dropped_pkts": "0",
        "out_uc_dropped_pkts": "0",
        "out_mc_dropped_pkts": "0",
    }


class AristaDropPrecedenceCounters(BaseModel):
    """Contains the drop precedence counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    dp0_dropped_pkts: Optional[int] = None
    dp1_dropped_pkts: Optional[int] = None
    dp2_dropped_pkts: Optional[int] = None

    error_fields: ClassVar[dict[str, str]] = {
        "dp0_dropped_pkts": "0",
        "dp1_dropped_pkts": "0",
        "dp2_dropped_pkts": "0",
    }


class AristaPerQueueCounters(BaseModel):
    """Contains the per-queue counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    txq: Optional[str] = None
    pkts_counter: Optional[int] = None
    bytes_counter: Optional[int] = None
    pkts_drop: Optional[int] = None
    bytes_drop: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "pkts_drop": "0",
        "bytes_drop": "0",
    }


class AristaPauseFrameCounters(BaseModel):
    """Contains the pause frame counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tx_admin_state: Optional[str] = None
    tx_oper_state: Optional[str] = None
    rx_admin_state: Optional[str] = None
    rx_oper_state: Optional[str] = None
    tx_pause: Optional[int] = None
    rx_pause: Optional[int] = None

    error_fields: ClassVar[dict[str, str]] = {
        "tx_pause": "0",
        "rx_pause": "0",
    }


# class AristaPfcWatchdogCounters(BaseModel):
#     """Contains the PFC watchdog counters for an Arista switch port."""
# add this when example is available, this command not supported on certain switches


class AristaEncCounters(BaseModel):
    """Contains the ENC counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    txq: Optional[str] = None
    marked_packets: Optional[str] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "marked_packets": "0",
    }


class AristaPfcCounters(BaseModel):
    """Contains the PFC counters for an Arista switch port."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    rx_frames: Optional[int] = None
    tx_frames: Optional[int] = None

    warning_fields: ClassVar[dict[str, str]] = {
        "rx_frames": "0",
        "tx_frames": "0",
    }


class PortData(BaseModel):
    """Contains all the data for a single port on an Arista switch."""

    port_status: Optional[AristaPortStatus] = None
    phy_status: Optional[AristaPhyStatus] = None
    error_counters: Optional[AristaCountersErrors] = None
    packet_counters: Optional[AristaPacketCounters] = None
    ip_counters: Optional[AristaIpCounters] = None
    out_bins_counters: Optional[AristaBinsCounters] = None
    in_bins_counters: Optional[AristaBinsCounters] = None
    rates_counters: Optional[AristaRatesCounters] = None
    dropped_packet_counters: Optional[AristaDroppedPacketCounters] = None
    dropped_precedence_counters: Optional[AristaDropPrecedenceCounters] = None
    per_queue_counters: Optional[List[AristaPerQueueCounters]] = None
    pause_frame_counters: Optional[AristaPauseFrameCounters] = None
    pfc_counters: Optional[AristaPfcCounters] = None
    # pfc_watchdog_counters: AristaPfcWatchdogCounters | None = None
    enc_counters: Optional[List[AristaEncCounters]] = None
    # mmu_queue_status, collect to file


class SwitchAristaDataModel(DataModel):
    """Collected output of Arista commands."""

    version: Optional[AristaVersion] = None
    lldp_neighbors: Optional[AristaNeighbors] = None
    system_env: Optional[AristaSystemEnv] = None
    port_list: Optional[List[str]] = None

    port: Optional[Dict[str, PortData]] = None
