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
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from nodescraper.models import DataModel


class NicCtlCardShow(BaseModel):
    """Outputs from global 'nicctl show card *' commands (flash, interrupts, logs, profile, time, statistics)."""

    flash_partition: Optional[Any] = None
    interrupts: Optional[Any] = None
    logs_non_persistent: Optional[str] = None
    logs_boot_fault: Optional[str] = None
    logs_persistent: Optional[str] = None
    profile: Optional[Any] = None
    time: Optional[Any] = None
    statistics_packet_buffer_summary: Optional[Any] = None


class NicCtlCard(BaseModel):
    """Per-card data: identity from 'nicctl show card' plus per-card commands (hardware-config, dcqcn)."""

    card_id: str
    info: Optional[Any] = Field(
        default=None, description="Card entry from nicctl show card --json list."
    )
    hardware_config: Optional[str] = Field(
        default=None, description="Raw stdout from nicctl show card hardware-config --card {id}."
    )
    dcqcn: Optional[Any] = Field(
        default=None, description="Parsed JSON from nicctl show dcqcn --card {id} --json."
    )


class NicCtlPort(BaseModel):
    """Outputs from 'nicctl show port *' commands."""

    port: Optional[Any] = Field(default=None, description="Parsed from nicctl show port --json.")
    port_fsm: Optional[str] = Field(
        default=None, description="Raw stdout from nicctl show port fsm."
    )
    port_transceiver: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show port transceiver --json."
    )
    port_statistics: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show port statistics --json."
    )
    port_internal_mac: Optional[str] = Field(
        default=None, description="Raw stdout from nicctl show port internal mac."
    )


class NicCtlLif(BaseModel):
    """Outputs from 'nicctl show lif *' commands."""

    lif: Optional[Any] = Field(default=None, description="Parsed from nicctl show lif --json.")
    lif_statistics: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show lif statistics --json."
    )
    lif_internal_queue_to_ud_pinning: Optional[str] = Field(
        default=None,
        description="Raw stdout from nicctl show lif internal queue-to-ud-pinning.",
    )


class NicCtlQos(BaseModel):
    """Outputs from 'nicctl show qos *' commands."""

    qos: Optional[Any] = Field(default=None, description="Parsed from nicctl show qos --json.")
    qos_headroom: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show qos headroom --json."
    )


class NicCtlRdma(BaseModel):
    """Outputs from 'nicctl show rdma *' commands."""

    rdma_queue: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show rdma queue --json."
    )
    rdma_queue_pair_detail: Optional[Any] = Field(
        default=None,
        description="Parsed from nicctl show rdma queue-pair --detail --json.",
    )
    rdma_statistics: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show rdma statistics --json."
    )


class NicCtlDcqcn(BaseModel):
    """Global DCQCN output; per-card DCQCN is in NicCtlCard.dcqcn."""

    dcqcn_global: Optional[Any] = Field(
        default=None, description="Parsed from nicctl show dcqcn --json."
    )


class NicCtlEnvironment(BaseModel):
    """Output from 'nicctl show environment'."""

    environment: Optional[Any] = None


class NicCtlVersion(BaseModel):
    """Version outputs from nicctl."""

    version: Optional[str] = Field(default=None, description="Raw stdout from nicctl --version.")
    version_firmware: Optional[str] = Field(
        default=None, description="Raw stdout from nicctl show version firmware."
    )


class NicCliDevice(BaseModel):
    """NIC device from niccli --list_devices (Broadcom)."""

    device_num: int
    model: Optional[str] = None
    adapter_port: Optional[str] = None
    interface_name: Optional[str] = None
    mac_address: Optional[str] = None
    pci_address: Optional[str] = None


class NicCliQosAppEntry(BaseModel):
    """APP TLV entry in niccli QoS output (Broadcom)."""

    priority: Optional[int] = None
    sel: Optional[int] = None
    dscp: Optional[int] = None
    protocol: Optional[str] = None
    port: Optional[int] = None


class NicCliQos(BaseModel):
    """NIC QoS from niccli -dev X getqos / qos --ets --show (Broadcom)."""

    device_num: int
    raw_output: str
    prio_map: Dict[int, int] = Field(default_factory=dict)
    tc_bandwidth: List[int] = Field(default_factory=list)
    tsa_map: Dict[int, str] = Field(default_factory=dict)
    pfc_enabled: Optional[int] = None
    app_entries: List[NicCliQosAppEntry] = Field(default_factory=list)
    tc_rate_limit: List[int] = Field(default_factory=list)


class PensandoNicCard(BaseModel):
    """Pensando NIC card from nicctl show card (text)."""

    id: str
    pcie_bdf: str
    asic: Optional[str] = None
    fw_partition: Optional[str] = None
    serial_number: Optional[str] = None


class PensandoNicDcqcn(BaseModel):
    """Pensando NIC DCQCN from nicctl show dcqcn (text)."""

    nic_id: str
    pcie_bdf: str
    lif_id: Optional[str] = None
    roce_device: Optional[str] = None
    dcqcn_profile_id: Optional[str] = None
    status: Optional[str] = None


class PensandoNicEnvironment(BaseModel):
    """Pensando NIC environment from nicctl show environment (text)."""

    nic_id: str
    pcie_bdf: str
    total_power_drawn: Optional[float] = None
    core_power: Optional[float] = None
    arm_power: Optional[float] = None
    local_board_temperature: Optional[float] = None
    die_temperature: Optional[float] = None
    input_voltage: Optional[float] = None
    core_voltage: Optional[float] = None
    core_frequency: Optional[float] = None
    cpu_frequency: Optional[float] = None
    p4_stage_frequency: Optional[float] = None


class PensandoNicPcieAts(BaseModel):
    """Pensando NIC PCIe ATS from nicctl show pcie ats (text)."""

    nic_id: str
    pcie_bdf: str
    status: str


class PensandoNicLif(BaseModel):
    """Pensando NIC LIF from nicctl show lif (text)."""

    nic_id: str
    pcie_bdf: str
    lif_id: str
    lif_name: Optional[str] = None


class PensandoNicPort(BaseModel):
    """Pensando NIC port from nicctl show port (text)."""

    nic_id: str
    pcie_bdf: str
    port_id: str
    port_name: str
    spec_ifindex: Optional[str] = None
    spec_type: Optional[str] = None
    spec_speed: Optional[str] = None
    spec_admin_state: Optional[str] = None
    spec_fec_type: Optional[str] = None
    spec_pause_type: Optional[str] = None
    spec_num_lanes: Optional[int] = None
    spec_mtu: Optional[int] = None
    spec_tx_pause: Optional[str] = None
    spec_rx_pause: Optional[str] = None
    spec_auto_negotiation: Optional[str] = None
    status_physical_port: Optional[int] = None
    status_operational_status: Optional[str] = None
    status_link_fsm_state: Optional[str] = None
    status_fec_type: Optional[str] = None
    status_cable_type: Optional[str] = None
    status_num_lanes: Optional[int] = None
    status_speed: Optional[str] = None
    status_auto_negotiation: Optional[str] = None
    status_mac_id: Optional[int] = None
    status_mac_channel: Optional[int] = None
    status_mac_address: Optional[str] = None
    status_transceiver_type: Optional[str] = None
    status_transceiver_state: Optional[str] = None
    status_transceiver_pid: Optional[str] = None


class PensandoNicQosScheduling(BaseModel):
    """QoS Scheduling entry."""

    priority: int
    scheduling_type: Optional[str] = None
    bandwidth: Optional[int] = None
    rate_limit: Optional[str] = None


class PensandoNicQos(BaseModel):
    """Pensando NIC QoS from nicctl show qos (text)."""

    nic_id: str
    pcie_bdf: str
    port_id: str
    classification_type: Optional[str] = None
    dscp_bitmap: Optional[str] = None
    dscp_range: Optional[str] = None
    dscp_priority: Optional[int] = None
    pfc_priority_bitmap: Optional[str] = None
    pfc_no_drop_priorities: Optional[str] = None
    scheduling: List[PensandoNicQosScheduling] = Field(default_factory=list)


class PensandoNicRdmaStatistic(BaseModel):
    """RDMA statistic entry."""

    name: str
    count: int


class PensandoNicRdmaStatistics(BaseModel):
    """Pensando NIC RDMA statistics from nicctl show rdma statistics (text)."""

    nic_id: str
    pcie_bdf: str
    statistics: List[PensandoNicRdmaStatistic] = Field(default_factory=list)


class PensandoNicVersionHostSoftware(BaseModel):
    """Pensando NIC host software version from nicctl show version host-software."""

    version: Optional[str] = None
    ipc_driver: Optional[str] = None
    ionic_driver: Optional[str] = None


class PensandoNicVersionFirmware(BaseModel):
    """Pensando NIC firmware version from nicctl show version firmware (text)."""

    nic_id: str
    pcie_bdf: str
    cpld: Optional[str] = None
    boot0: Optional[str] = None
    uboot_a: Optional[str] = None
    firmware_a: Optional[str] = None
    device_config_a: Optional[str] = None


def command_to_canonical_key(command: str) -> str:
    """Turn a full command string into a stable key.

    E.g. 'nicctl show card --json' -> 'nicctl_show_card_json',
         'nicctl show dcqcn --card 0 --json' -> 'nicctl_show_dcqcn_card_0_json'.
    """
    s = command.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"--+", "_", s)
    s = s.strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "unknown"


class NicCommandResult(BaseModel):
    """Result of a single niccli/nicctl command run."""

    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    @property
    def succeeded(self) -> bool:
        """True if the command exited with code 0."""
        return self.exit_code == 0


class NicDataModel(DataModel):
    """Collected output of niccli (Broadcom) and nicctl (Pensando) commands."""

    results: Dict[str, NicCommandResult] = Field(default_factory=dict)

    # Structured by domain (parsed from command output in collector)
    card_show: Optional[NicCtlCardShow] = Field(
        default=None, description="Global nicctl show card * outputs."
    )
    cards: List[NicCtlCard] = Field(
        default_factory=list, description="Per-card data (card list + hardware-config, dcqcn)."
    )
    port: Optional[NicCtlPort] = None
    lif: Optional[NicCtlLif] = None
    qos: Optional[NicCtlQos] = None
    rdma: Optional[NicCtlRdma] = None
    dcqcn: Optional[NicCtlDcqcn] = None
    environment: Optional[NicCtlEnvironment] = None
    version: Optional[NicCtlVersion] = None

    broadcom_nic_devices: List[NicCliDevice] = Field(default_factory=list)
    broadcom_nic_qos: Dict[int, NicCliQos] = Field(default_factory=dict)
    broadcom_nic_support_rdma: Dict[int, str] = Field(
        default_factory=dict,
        description="Per-device output of 'niccli -dev X nvm -getoption support_rdma -scope 0' (device_num -> raw stdout).",
    )
    broadcom_nic_performance_profile: Dict[int, str] = Field(
        default_factory=dict,
        description="Per-device output of 'niccli -dev X nvm -getoption performance_profile' (device_num -> raw stdout).",
    )
    broadcom_nic_pcie_relaxed_ordering: Dict[int, str] = Field(
        default_factory=dict,
        description="Per-device output of 'niccli -dev X nvm -getoption pcie_relaxed_ordering' (device_num -> raw stdout).",
    )
    pensando_nic_cards: List[PensandoNicCard] = Field(default_factory=list)
    pensando_nic_dcqcn: List[PensandoNicDcqcn] = Field(default_factory=list)
    pensando_nic_environment: List[PensandoNicEnvironment] = Field(default_factory=list)
    pensando_nic_lif: List[PensandoNicLif] = Field(default_factory=list)
    pensando_nic_pcie_ats: List[PensandoNicPcieAts] = Field(default_factory=list)
    pensando_nic_ports: List[PensandoNicPort] = Field(default_factory=list)
    pensando_nic_qos: List[PensandoNicQos] = Field(default_factory=list)
    pensando_nic_rdma_statistics: List[PensandoNicRdmaStatistics] = Field(default_factory=list)
    pensando_nic_version_host_software: Optional[PensandoNicVersionHostSoftware] = None
    pensando_nic_version_firmware: List[PensandoNicVersionFirmware] = Field(default_factory=list)

    def command_succeeded(self, command: str) -> bool:
        """Return True if the command ran and exited with code 0."""
        r = self.results.get(command)
        return r is not None and r.succeeded

    def get_card(self, card_id: str) -> Optional[NicCtlCard]:
        """Return the per-card data for the given card id."""
        for c in self.cards:
            if c.card_id == card_id:
                return c
        return None
