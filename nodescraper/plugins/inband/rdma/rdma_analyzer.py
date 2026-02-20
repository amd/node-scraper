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
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .rdmadata import RdmaDataModel


class RdmaAnalyzer(DataAnalyzer[RdmaDataModel, None]):
    """Check RDMA statistics for errors (RoCE and other RDMA error counters)."""

    DATA_MODEL = RdmaDataModel

    # Error fields checked from rdma statistic output (bnxt_re, mlx5, ionic, etc.)
    ERROR_FIELDS = [
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
        "unrecoverable_err",
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
        "res_mem_err",
        "res_srq_err",
        "res_cmp_err",
        "res_invalid_dup_rkey",
        "res_wqe_format_err",
        "res_cq_load_err",
        "res_srq_load_err",
        "res_tx_pci_err",
        "res_rx_pci_err",
        "out_of_buffer",
        "out_of_sequence",
        "req_cqe_error",
        "req_cqe_flush_error",
        "resp_cqe_error",
        "resp_cqe_flush_error",
        "resp_remote_access_errors",
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
        "rx_rdma_mtu_discard_pkts",
    ]

    CRITICAL_ERROR_FIELDS = [
        "unrecoverable_err",
        "res_tx_pci_err",
        "res_rx_pci_err",
        "res_mem_err",
    ]

    def analyze_data(self, data: RdmaDataModel, args: Optional[None] = None) -> TaskResult:
        """Analyze RDMA statistics for non-zero error counters.

        Args:
            data: RDMA data model with statistic_list (and optionally link_list).
            args: Unused (analyzer has no configurable args).

        Returns:
            TaskResult with status OK if no errors, ERROR if any error counter > 0.
        """
        if not data.statistic_list:
            self.result.message = "RDMA statistics list is empty"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        error_state = False
        for idx, stat in enumerate(data.statistic_list):
            for error_field in self.ERROR_FIELDS:
                value = getattr(stat, error_field, None)
                if value is not None and value > 0:
                    priority = (
                        EventPriority.CRITICAL
                        if error_field in self.CRITICAL_ERROR_FIELDS
                        else EventPriority.ERROR
                    )
                    self._log_event(
                        category=EventCategory.IO,
                        description=f"RDMA error detected: {error_field}",
                        data={
                            "interface": stat.ifname,
                            "port": stat.port,
                            "error_field": error_field,
                            "error_count": value,
                            "statistic_index": idx,
                        },
                        priority=priority,
                        console_log=True,
                    )
                    error_state = True

        if error_state:
            self.result.message = "RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.ERROR
        else:
            self.result.message = "No RDMA errors detected in statistics"
            self.result.status = ExecutionStatus.OK
        return self.result
