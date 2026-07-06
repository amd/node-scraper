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
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

from nodescraper.models import DataModel


class PollaraRdmaStatistics(BaseModel):
    """ifname ionic"""

    tx_rdma_ucast_bytes: Optional[int] = None
    tx_rdma_ucast_pkts: Optional[int] = None
    tx_rdma_mcast_bytes: Optional[int] = None
    tx_rdma_mcast_pkts: Optional[int] = None
    tx_rdma_cnp_pkts: Optional[int] = None
    rx_rdma_ucast_bytes: Optional[int] = None
    rx_rdma_ucast_pkts: Optional[int] = None
    rx_rdma_mcast_bytes: Optional[int] = None
    rx_rdma_mcast_pkts: Optional[int] = None
    rx_rdma_cnp_pkts: Optional[int] = None
    rx_rdma_ecn_pkts: Optional[int] = None
    req_rx_pkt_seq_err: Optional[int] = None
    req_rx_rnr_retry_err: Optional[int] = None
    req_rx_rmt_acc_err: Optional[int] = None
    req_rx_rmt_req_err: Optional[int] = None
    req_rx_oper_err: Optional[int] = None
    req_rx_impl_nak_seq_err: Optional[int] = None
    req_rx_cqe_err: Optional[int] = None
    req_rx_cqe_flush: Optional[int] = None
    req_rx_dup_response: Optional[int] = None
    req_rx_inval_pkts: Optional[int] = None
    req_tx_loc_acc_err: Optional[int] = None
    req_tx_loc_oper_err: Optional[int] = None
    req_tx_mem_mgmt_err: Optional[int] = None
    req_tx_retry_excd_err: Optional[int] = None
    req_tx_loc_sgl_inv_err: Optional[int] = None
    resp_rx_dup_request: Optional[int] = None
    resp_rx_outof_buf: Optional[int] = None
    resp_rx_outouf_seq: Optional[int] = None
    resp_rx_cqe_err: Optional[int] = None
    resp_rx_cqe_flush: Optional[int] = None
    resp_rx_loc_len_err: Optional[int] = None
    resp_rx_inval_request: Optional[int] = None
    resp_rx_loc_oper_err: Optional[int] = None
    resp_rx_outof_atomic: Optional[int] = None
    resp_tx_pkt_seq_err: Optional[int] = None
    resp_tx_rmt_inval_req_err: Optional[int] = None
    resp_tx_rmt_acc_err: Optional[int] = None
    resp_tx_rmt_oper_err: Optional[int] = None
    resp_tx_rnr_retry_err: Optional[int] = None
    resp_tx_loc_sgl_inv_err: Optional[int] = None
    resp_rx_s0_table_err: Optional[int] = None
    tx_rdma_ccl_cts_bytes: Optional[int] = None
    tx_rdma_ccl_cts_pkts: Optional[int] = None
    rx_rdma_ccl_cts_bytes: Optional[int] = None
    rx_rdma_ccl_cts_pkts: Optional[int] = None
    resp_rx_ccl_cts_outouf_seq: Optional[int] = None
    tx_rdma_ack_timeout: Optional[int] = None
    tx_rdma_ccl_cts_ack_timeout: Optional[int] = None
    tx_rdma_retx_bytes: Optional[int] = None
    tx_rdma_retx_pkts: Optional[int] = None
    tx_rdma_ccl_cts_retx_bytes: Optional[int] = None
    tx_rdma_ccl_cts_retx_pkts: Optional[int] = None
    rx_rdma_mtu_discard_pkts: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "req_rx_pkt_seq_err",
        "req_rx_rnr_retry_err",
        "req_rx_rmt_acc_err",
        "req_rx_rmt_req_err",
        "req_rx_oper_err",
        "req_rx_impl_nak_seq_err",
        "req_rx_cqe_err",
        "req_rx_cqe_flush",
        "req_rx_dup_response",
        "req_rx_inval_pkts",
        "req_tx_loc_acc_err",
        "req_tx_loc_oper_err",
        "req_tx_mem_mgmt_err",
        "req_tx_retry_excd_err",
        "req_tx_loc_sgl_inv_err",
        "resp_rx_dup_request",
        "resp_rx_outof_buf",
        "resp_rx_outouf_seq",
        "resp_rx_cqe_err",
        "resp_rx_cqe_flush",
        "resp_rx_loc_len_err",
        "resp_rx_inval_request",
        "resp_rx_loc_oper_err",
        "resp_rx_outof_atomic",
        "resp_tx_pkt_seq_err",
        "resp_tx_rmt_inval_req_err",
        "resp_tx_rmt_acc_err",
        "resp_tx_rmt_oper_err",
        "resp_tx_rnr_retry_err",
        "resp_tx_loc_sgl_inv_err",
        "resp_rx_s0_table_err",
        "resp_rx_ccl_cts_outouf_seq",
        "tx_rdma_ack_timeout",
        "tx_rdma_ccl_cts_ack_timeout",
        "tx_rdma_retx_bytes",
        "tx_rdma_retx_pkts",
        "tx_rdma_ccl_cts_retx_bytes",
        "tx_rdma_ccl_cts_retx_pkts",
        "rx_rdma_mtu_discard_pkts",
    ]

    critical_error_fields: ClassVar[list[str]] = []


class Thor2RdmaStatistics(BaseModel):
    """ifname bnxt"""

    active_pds: Optional[int] = None
    active_ahs: Optional[int] = None
    active_qps: Optional[int] = None
    active_rc_qps: Optional[int] = None
    active_ud_qps: Optional[int] = None
    active_srqs: Optional[int] = None
    active_cqs: Optional[int] = None
    active_mrs: Optional[int] = None
    active_mws: Optional[int] = None
    watermark_pds: Optional[int] = None
    watermark_ahs: Optional[int] = None
    watermark_qps: Optional[int] = None
    watermark_rc_qps: Optional[int] = None
    watermark_ud_qps: Optional[int] = None
    watermark_srqs: Optional[int] = None
    watermark_cqs: Optional[int] = None
    watermark_mrs: Optional[int] = None
    watermark_mws: Optional[int] = None
    rx_pkts: Optional[int] = None
    rx_bytes: Optional[int] = None
    tx_pkts: Optional[int] = None
    tx_bytes: Optional[int] = None
    recoverable_errors: Optional[int] = None
    tx_roce_errors: Optional[int] = None
    tx_roce_discards: Optional[int] = None
    rx_roce_errors: Optional[int] = None
    rx_roce_discards: Optional[int] = None
    local_ack_timeout_err: Optional[int] = None
    packet_seq_err: Optional[int] = None
    max_retry_exceeded: Optional[int] = None
    rnr_nak_retry_err: Optional[int] = None
    implied_nak_seq_err: Optional[int] = None
    unrecoverable_err: Optional[int] = None
    bad_resp_err: Optional[int] = None
    local_qp_op_err: Optional[int] = None
    local_protection_err: Optional[int] = None
    mem_mgmt_op_err: Optional[int] = None
    req_remote_invalid_request: Optional[int] = None
    req_remote_access_errors: Optional[int] = None
    remote_op_err: Optional[int] = None
    duplicate_request: Optional[int] = None
    res_exceed_max: Optional[int] = None
    resp_local_length_error: Optional[int] = None
    res_exceeds_wqe: Optional[int] = None
    res_opcode_err: Optional[int] = None
    res_rx_invalid_rkey: Optional[int] = None
    res_rx_domain_err: Optional[int] = None
    res_rx_no_perm: Optional[int] = None
    res_rx_range_err: Optional[int] = None
    res_tx_invalid_rkey: Optional[int] = None
    res_tx_domain_err: Optional[int] = None
    res_tx_no_perm: Optional[int] = None
    res_tx_range_err: Optional[int] = None
    res_irrq_oflow: Optional[int] = None
    res_unsup_opcode: Optional[int] = None
    res_unaligned_atomic: Optional[int] = None
    res_rem_inv_err: Optional[int] = None
    res_mem_err: Optional[int] = None
    res_srq_err: Optional[int] = None
    res_cmp_err: Optional[int] = None
    res_invalid_dup_rkey: Optional[int] = None
    res_wqe_format_err: Optional[int] = None
    res_cq_load_err: Optional[int] = None
    res_srq_load_err: Optional[int] = None
    res_tx_pci_err: Optional[int] = None
    res_rx_pci_err: Optional[int] = None
    tx_atomic_req: Optional[int] = None
    tx_read_req: Optional[int] = None
    tx_read_resp: Optional[int] = None
    tx_write_req: Optional[int] = None
    tx_send_req: Optional[int] = None
    rx_atomic_requests: Optional[int] = None
    rx_read_requests: Optional[int] = None
    rx_read_resp: Optional[int] = None
    rx_write_requests: Optional[int] = None
    rx_send_req: Optional[int] = None
    rx_good_pkts: Optional[int] = None
    rx_good_bytes: Optional[int] = None
    out_of_buffer: Optional[int] = None
    np_cnp_sent: Optional[int] = None
    rp_cnp_handled: Optional[int] = None
    np_ecn_marked_roce_packets: Optional[int] = None
    out_of_sequence: Optional[int] = None
    pacing_reschedule: Optional[int] = None
    pacing_complete: Optional[int] = None
    pacing_alerts: Optional[int] = None
    db_fifo_register: Optional[int] = None
    req_cqe_error: Optional[int] = None
    req_cqe_flush_error: Optional[int] = None
    resp_cqe_error: Optional[int] = None
    resp_cqe_flush_error: Optional[int] = None
    resp_remote_access_errors: Optional[int] = None
    roce_adp_retrans: Optional[int] = None
    roce_adp_retrans_to: Optional[int] = None
    roce_slow_restart: Optional[int] = None
    roce_slow_restart_cnps: Optional[int] = None
    roce_slow_restart_trans: Optional[int] = None
    rp_cnp_ignored: Optional[int] = None
    rx_icrc_encapsulated: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "recoverable_errors",
        "tx_roce_errors",
        "tx_roce_discards",
        "rx_roce_errors",
        "rx_roce_discards",
        "local_ack_timeout_err",
        "packet_seq_err",
        "max_retry_exceeded",
        "rnr_nak_retry_err",
        "implied_nak_seq_err",
        "bad_resp_err",
        "local_qp_op_err",
        "local_protection_err",
        "mem_mgmt_op_err",
        "req_remote_invalid_request",
        "req_remote_access_errors",
        "remote_op_err",
        "duplicate_request",
        "res_exceed_max",
        "resp_local_length_error",
        "res_exceeds_wqe",
        "res_opcode_err",
        "res_rx_invalid_rkey",
        "res_rx_domain_err",
        "res_rx_no_perm",
        "res_rx_range_err",
        "res_tx_invalid_rkey",
        "res_tx_domain_err",
        "res_tx_no_perm",
        "res_tx_range_err",
        "res_irrq_oflow",
        "res_unsup_opcode",
        "res_unaligned_atomic",
        "res_rem_inv_err",
        "res_srq_err",
        "res_cmp_err",
        "res_invalid_dup_rkey",
        "res_wqe_format_err",
        "res_cq_load_err",
        "res_srq_load_err",
        "out_of_buffer",
        "out_of_sequence",
        "req_cqe_error",
        "req_cqe_flush_error",
        "resp_cqe_error",
        "resp_cqe_flush_error",
        "resp_remote_access_errors",
        "roce_adp_retrans",
        "roce_adp_retrans_to",
        "rp_cnp_ignored",
        "rx_icrc_encapsulated",
    ]

    critical_error_fields: ClassVar[list[str]] = [
        "unrecoverable_err",
        "res_tx_pci_err",
        "res_rx_pci_err",
        "res_mem_err",
    ]


class Cx7RdmaStatistics(BaseModel):
    """ifname mlx"""

    rx_write_requests: Optional[int] = None
    rx_read_requests: Optional[int] = None
    rx_atomic_requests: Optional[int] = None
    rx_dct_connect: Optional[int] = None
    out_of_buffer: Optional[int] = None
    out_of_sequence: Optional[int] = None
    duplicate_request: Optional[int] = None
    rnr_nak_retry_err: Optional[int] = None
    packet_seq_err: Optional[int] = None
    implied_nak_seq_err: Optional[int] = None
    local_ack_timeout_err: Optional[int] = None
    resp_local_length_error: Optional[int] = None
    resp_cqe_error: Optional[int] = None
    req_cqe_error: Optional[int] = None
    req_remote_invalid_request: Optional[int] = None
    req_remote_access_errors: Optional[int] = None
    resp_remote_access_errors: Optional[int] = None
    resp_cqe_flush_error: Optional[int] = None
    req_cqe_flush_error: Optional[int] = None
    roce_adp_retrans: Optional[int] = None
    roce_adp_retrans_to: Optional[int] = None
    roce_slow_restart: Optional[int] = None
    roce_slow_restart_cnps: Optional[int] = None
    roce_slow_restart_trans: Optional[int] = None
    rp_cnp_ignored: Optional[int] = None
    rp_cnp_handled: Optional[int] = None
    np_ecn_marked_roce_packets: Optional[int] = None
    np_cnp_sent: Optional[int] = None
    rx_icrc_encapsulated: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "out_of_buffer",
        "out_of_sequence",
        "duplicate_request",
        "rnr_nak_retry_err",
        "packet_seq_err",
        "implied_nak_seq_err",
        "local_ack_timeout_err",
        "resp_local_length_error",
        "resp_cqe_error",
        "req_cqe_error",
        "req_remote_invalid_request",
        "req_remote_access_errors",
        "resp_remote_access_errors",
        "resp_cqe_flush_error",
        "req_cqe_flush_error",
        "roce_adp_retrans",
        "roce_adp_retrans_to",
        "rp_cnp_ignored",
        "rx_icrc_encapsulated",
    ]

    critical_error_fields: ClassVar[list[str]] = []


RdmaVendorStatistics = Union[PollaraRdmaStatistics, Thor2RdmaStatistics, Cx7RdmaStatistics]

# Map ifname prefixes to vendor-specific statistic models
VENDOR_PREFIX_MAP: dict[str, type[RdmaVendorStatistics]] = {
    "ionic": PollaraRdmaStatistics,
    "bnxt": Thor2RdmaStatistics,
    "mlx": Cx7RdmaStatistics,
}


class RdmaStatistics(BaseModel):
    # Interface information
    ifname: Optional[str] = None
    netdev: Optional[str] = None
    port: Optional[int] = None
    vendor_statistics: Optional[RdmaVendorStatistics] = None

    @model_validator(mode="after")
    def validate_atleast_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be set in RdmaStatistics")
        return self


class RdmaLink(BaseModel):
    # Interface and port information
    ifindex: Optional[int] = None
    ifname: Optional[str] = None
    port: Optional[int] = None
    state: Optional[str] = None
    physical_state: Optional[str] = None
    netdev: Optional[str] = None
    netdev_index: Optional[int] = None

    @model_validator(mode="after")
    def validate_atleast_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be set in RdmaLink")
        return self


class RdmaDevice(BaseModel):
    """RDMA device from 'rdma dev' (text output)."""

    device: str
    node_type: Optional[str] = None
    transport: Optional[str] = None
    node_guid: Optional[str] = None
    sys_image_guid: Optional[str] = None
    state: Optional[str] = None
    attributes: dict[str, str] = Field(default_factory=dict)


class RdmaLinkText(BaseModel):
    """RDMA link from 'rdma link' (text output)."""

    device: str
    port: int
    state: Optional[str] = None
    physical_state: Optional[str] = None
    netdev: Optional[str] = None
    attributes: dict[str, str] = Field(default_factory=dict)


class RdmaDataModel(DataModel):
    """
    Data model for RDMA (Remote Direct Memory Access) statistics and link information.

    Attributes:
        statistic_list: RDMA statistics from 'rdma statistic -j'. Each entry has
            ifname, port, and vendor_statistics (ionic/bnxt/mlx counters) when the
            interface prefix matches a known vendor.
        link_list: RDMA links from 'rdma link -j' (JSON).
        dev_list: RDMA devices from 'rdma dev' (text).
        link_list_text: RDMA links from 'rdma link' (text).
    """

    link_list: list[RdmaLink] = Field(default_factory=list)
    statistic_list: list[RdmaStatistics] = Field(default_factory=list)
    dev_list: list[RdmaDevice] = Field(default_factory=list)
    link_list_text: list[RdmaLinkText] = Field(default_factory=list)
