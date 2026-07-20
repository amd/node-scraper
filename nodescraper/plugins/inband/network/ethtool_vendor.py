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
"""Vendor-specific ethtool -S statistics models (Pollara / Thor2 / ConnectX-7)."""

import re
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class PollaraEthtoolStatistics(BaseModel):
    """ionic (Pollara) ethtool -S counters."""

    #: Regex matched against raw ``ethtool -S`` field names to identify per-queue
    queue_counter_regex: ClassVar[str] = r"^(rx|tx)_\d+"
    queue_error_regex: ClassVar[list[str]] = [
        r"dma_map_err",
        r"hwstamp_invalid",
        r"alloc_err",
        r"csum_error",
        r"dropped",
    ]
    queue_warning_regex: ClassVar[list[str]] = []

    rx_csum_error: Optional[int] = None
    hw_tx_dropped: Optional[int] = None
    hw_rx_dropped: Optional[int] = None
    hw_rx_over_errors: Optional[int] = None
    hw_rx_missed_errors: Optional[int] = None
    hw_tx_aborted_errors: Optional[int] = None
    frames_rx_bad_fcs: Optional[int] = None
    frames_rx_bad_all: Optional[int] = None
    frames_rx_pause: Optional[int] = None
    frames_rx_bad_length: Optional[int] = None
    frames_rx_undersized: Optional[int] = None
    frames_rx_oversized: Optional[int] = None
    frames_rx_fragments: Optional[int] = None
    frames_rx_jabber: Optional[int] = None
    frames_rx_pripause: Optional[int] = None
    frames_rx_stomped_crc: Optional[int] = None
    frames_rx_too_long: Optional[int] = None
    frames_rx_dropped: Optional[int] = None
    frames_rx_less_than_64b: Optional[int] = None
    frames_tx_bad: Optional[int] = None
    frames_tx_pause: Optional[int] = None
    frames_tx_pripause: Optional[int] = None
    frames_tx_less_than_64b: Optional[int] = None
    frames_tx_pri_0: Optional[int] = None
    frames_tx_pri_1: Optional[int] = None
    frames_tx_pri_2: Optional[int] = None
    frames_tx_pri_3: Optional[int] = None
    frames_tx_pri_4: Optional[int] = None
    frames_tx_pri_5: Optional[int] = None
    frames_tx_pri_6: Optional[int] = None
    frames_tx_pri_7: Optional[int] = None
    frames_rx_pri_0: Optional[int] = None
    frames_rx_pri_1: Optional[int] = None
    frames_rx_pri_2: Optional[int] = None
    frames_rx_pri_3: Optional[int] = None
    frames_rx_pri_4: Optional[int] = None
    frames_rx_pri_5: Optional[int] = None
    frames_rx_pri_6: Optional[int] = None
    frames_rx_pri_7: Optional[int] = None
    tx_pripause_0_1us_count: Optional[int] = None
    tx_pripause_1_1us_count: Optional[int] = None
    tx_pripause_2_1us_count: Optional[int] = None
    tx_pripause_3_1us_count: Optional[int] = None
    tx_pripause_4_1us_count: Optional[int] = None
    tx_pripause_5_1us_count: Optional[int] = None
    tx_pripause_6_1us_count: Optional[int] = None
    tx_pripause_7_1us_count: Optional[int] = None
    rx_pripause_0_1us_count: Optional[int] = None
    rx_pripause_1_1us_count: Optional[int] = None
    rx_pripause_2_1us_count: Optional[int] = None
    rx_pripause_3_1us_count: Optional[int] = None
    rx_pripause_4_1us_count: Optional[int] = None
    rx_pripause_5_1us_count: Optional[int] = None
    rx_pripause_6_1us_count: Optional[int] = None
    rx_pripause_7_1us_count: Optional[int] = None
    rx_pause_1us_count: Optional[int] = None
    frames_tx_truncated: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "rx_csum_error",
        "hw_tx_dropped",
        "hw_rx_dropped",
        "hw_rx_over_errors",
        "hw_rx_missed_errors",
        "hw_tx_aborted_errors",
        "frames_rx_bad_fcs",
        "frames_rx_bad_all",
        "frames_rx_bad_length",
        "frames_rx_undersized",
        "frames_rx_oversized",
        "frames_rx_fragments",
        "frames_rx_jabber",
        "frames_rx_stomped_crc",
        "frames_rx_too_long",
        "frames_rx_dropped",
        "frames_rx_less_than_64b",
        "frames_tx_bad",
        "frames_tx_less_than_64b",
        "frames_tx_truncated",
    ]

    warning_fields: ClassVar[list[str]] = [
        "frames_rx_pause",
        "frames_rx_pripause",
        "frames_tx_pause",
        "frames_tx_pripause",
        "frames_tx_pri_0",
        "frames_tx_pri_1",
        "frames_tx_pri_2",
        "frames_tx_pri_3",
        "frames_tx_pri_4",
        "frames_tx_pri_5",
        "frames_tx_pri_6",
        "frames_tx_pri_7",
        "tx_pripause_0_1us_count",
        "tx_pripause_1_1us_count",
        "tx_pripause_2_1us_count",
        "tx_pripause_3_1us_count",
        "tx_pripause_4_1us_count",
        "tx_pripause_5_1us_count",
        "tx_pripause_6_1us_count",
        "tx_pripause_7_1us_count",
        "frames_rx_pri_0",
        "frames_rx_pri_1",
        "frames_rx_pri_2",
        "frames_rx_pri_3",
        "frames_rx_pri_4",
        "frames_rx_pri_5",
        "frames_rx_pri_6",
        "frames_rx_pri_7",
        "rx_pripause_0_1us_count",
        "rx_pripause_1_1us_count",
        "rx_pripause_2_1us_count",
        "rx_pripause_3_1us_count",
        "rx_pripause_4_1us_count",
        "rx_pripause_5_1us_count",
        "rx_pripause_6_1us_count",
        "rx_pripause_7_1us_count",
        "rx_pause_1us_count",
    ]


class Thor2EthtoolStatistics(BaseModel):
    """bnxt (Thor2) ethtool -S counters."""

    #: Regex matched against raw ``ethtool -S`` field names to identify per-queue
    queue_counter_regex: ClassVar[str] = r"^\[\d+\]"
    queue_error_regex: ClassVar[list[str]] = [
        r"rx_discards",
        r"rx_errors",
        r"tx_errors",
        r"tx_discards",
        r"rx_l4_csum_errors",
        r"rx_buf_errors",
        r"so_txtime_cmpl_errors",
        r"missed_irqs",
        r"xsk_rx_redirect_fail",
        r"xsk_rx_alloc_fail",
        r"xsk_rx_no_room",
        r"xsk_tx_ring_full",
    ]
    queue_warning_regex: ClassVar[list[str]] = [
        r"rx_resets",
    ]

    rx_total_l4_csum_errors: Optional[int] = None
    rx_total_resets: Optional[int] = None
    rx_total_buf_errors: Optional[int] = None
    rx_total_oom_discards: Optional[int] = None
    rx_total_netpoll_discards: Optional[int] = None
    rx_total_ring_discards: Optional[int] = None
    tx_total_resets: Optional[int] = None
    tx_total_ring_discards: Optional[int] = None
    total_missed_irqs: Optional[int] = None
    ktls_tx_rec_err: Optional[int] = None
    ktls_rx_resync_discard: Optional[int] = None
    rx_fcs_err_frames: Optional[int] = None
    rx_pause_frames: Optional[int] = None
    rx_pfc_frames: Optional[int] = None
    rx_align_err_frames: Optional[int] = None
    rx_ovrsz_frames: Optional[int] = None
    rx_jbr_frames: Optional[int] = None
    rx_mtu_err_frames: Optional[int] = None
    rx_pfc_ena_frames_pri0: Optional[int] = None
    rx_pfc_ena_frames_pri1: Optional[int] = None
    rx_pfc_ena_frames_pri2: Optional[int] = None
    rx_pfc_ena_frames_pri3: Optional[int] = None
    rx_pfc_ena_frames_pri4: Optional[int] = None
    rx_pfc_ena_frames_pri5: Optional[int] = None
    rx_pfc_ena_frames_pri6: Optional[int] = None
    rx_pfc_ena_frames_pri7: Optional[int] = None
    rx_undrsz_frames: Optional[int] = None
    rx_runt_bytes: Optional[int] = None
    rx_runt_frames: Optional[int] = None
    rx_stat_discard: Optional[int] = None
    rx_stat_err: Optional[int] = None
    tx_pause_frames: Optional[int] = None
    tx_pfc_frames: Optional[int] = None
    tx_jabber_frames: Optional[int] = None
    tx_fcs_err_frames: Optional[int] = None
    tx_err: Optional[int] = None
    tx_fifo_underruns: Optional[int] = None
    tx_pfc_ena_frames_pri0: Optional[int] = None
    tx_pfc_ena_frames_pri1: Optional[int] = None
    tx_pfc_ena_frames_pri2: Optional[int] = None
    tx_pfc_ena_frames_pri3: Optional[int] = None
    tx_pfc_ena_frames_pri4: Optional[int] = None
    tx_pfc_ena_frames_pri5: Optional[int] = None
    tx_pfc_ena_frames_pri6: Optional[int] = None
    tx_pfc_ena_frames_pri7: Optional[int] = None
    tx_total_collisions: Optional[int] = None
    tx_stat_discard: Optional[int] = None
    tx_stat_error: Optional[int] = None
    link_down_events: Optional[int] = None
    continuous_pause_events: Optional[int] = None
    resume_pause_events: Optional[int] = None
    continuous_roce_pause_events: Optional[int] = None
    resume_roce_pause_events: Optional[int] = None
    pfc_pri0_rx_transitions: Optional[int] = None
    pfc_pri1_rx_transitions: Optional[int] = None
    pfc_pri2_rx_transitions: Optional[int] = None
    pfc_pri3_rx_transitions: Optional[int] = None
    pfc_pri4_rx_transitions: Optional[int] = None
    pfc_pri5_rx_transitions: Optional[int] = None
    pfc_pri6_rx_transitions: Optional[int] = None
    pfc_pri7_rx_transitions: Optional[int] = None
    rx_pcs_symbol_err: Optional[int] = None
    rx_discard_bytes_cos0: Optional[int] = None
    rx_discard_packets_cos0: Optional[int] = None
    rx_discard_bytes_cos1: Optional[int] = None
    rx_discard_packets_cos1: Optional[int] = None
    rx_discard_bytes_cos2: Optional[int] = None
    rx_discard_packets_cos2: Optional[int] = None
    rx_discard_bytes_cos3: Optional[int] = None
    rx_discard_packets_cos3: Optional[int] = None
    rx_discard_bytes_cos4: Optional[int] = None
    rx_discard_packets_cos4: Optional[int] = None
    rx_discard_bytes_cos5: Optional[int] = None
    rx_discard_packets_cos5: Optional[int] = None
    rx_discard_bytes_cos6: Optional[int] = None
    rx_discard_packets_cos6: Optional[int] = None
    rx_discard_bytes_cos7: Optional[int] = None
    rx_discard_packets_cos7: Optional[int] = None
    rx_fec_uncorrectable_blocks: Optional[int] = None
    rx_filter_miss: Optional[int] = None
    pfc_pri0_tx_transitions: Optional[int] = None
    pfc_pri1_tx_transitions: Optional[int] = None
    pfc_pri2_tx_transitions: Optional[int] = None
    pfc_pri3_tx_transitions: Optional[int] = None
    pfc_pri4_tx_transitions: Optional[int] = None
    pfc_pri5_tx_transitions: Optional[int] = None
    pfc_pri6_tx_transitions: Optional[int] = None
    pfc_pri7_tx_transitions: Optional[int] = None
    hw_db_recov_dbs_dropped: Optional[int] = None
    hw_db_recov_oo_drop_count: Optional[int] = None
    lpbk_tx_discards: Optional[int] = None
    lpbk_tx_errors: Optional[int] = None
    lpbk_rx_discards: Optional[int] = None
    lpbk_rx_errors: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "rx_total_l4_csum_errors",
        "rx_total_buf_errors",
        "rx_total_oom_discards",
        "rx_total_netpoll_discards",
        "rx_total_ring_discards",
        "tx_total_ring_discards",
        "total_missed_irqs",
        "ktls_tx_rec_err",
        "ktls_rx_resync_discard",
        "rx_fcs_err_frames",
        "rx_align_err_frames",
        "rx_ovrsz_frames",
        "rx_jbr_frames",
        "rx_mtu_err_frames",
        "rx_undrsz_frames",
        "rx_runt_bytes",
        "rx_runt_frames",
        "rx_stat_discard",
        "rx_stat_err",
        "tx_jabber_frames",
        "tx_fcs_err_frames",
        "tx_err",
        "tx_fifo_underruns",
        "tx_total_collisions",
        "tx_stat_discard",
        "tx_stat_error",
        "link_down_events",
        "rx_pcs_symbol_err",
        "rx_discard_bytes_cos0",
        "rx_discard_packets_cos0",
        "rx_discard_bytes_cos1",
        "rx_discard_packets_cos1",
        "rx_discard_bytes_cos2",
        "rx_discard_packets_cos2",
        "rx_discard_bytes_cos3",
        "rx_discard_packets_cos3",
        "rx_discard_bytes_cos4",
        "rx_discard_packets_cos4",
        "rx_discard_bytes_cos5",
        "rx_discard_packets_cos5",
        "rx_discard_bytes_cos6",
        "rx_discard_packets_cos6",
        "rx_discard_bytes_cos7",
        "rx_discard_packets_cos7",
        "rx_fec_uncorrectable_blocks",
        "rx_filter_miss",
        "hw_db_recov_dbs_dropped",
        "hw_db_recov_oo_drop_count",
        "lpbk_tx_discards",
        "lpbk_tx_errors",
        "lpbk_rx_discards",
        "lpbk_rx_errors",
    ]

    warning_fields: ClassVar[list[str]] = [
        "rx_total_resets",
        "tx_total_resets",
        "rx_pause_frames",
        "rx_pfc_frames",
        "rx_pfc_ena_frames_pri0",
        "rx_pfc_ena_frames_pri1",
        "rx_pfc_ena_frames_pri2",
        "rx_pfc_ena_frames_pri3",
        "rx_pfc_ena_frames_pri4",
        "rx_pfc_ena_frames_pri5",
        "rx_pfc_ena_frames_pri6",
        "rx_pfc_ena_frames_pri7",
        "pfc_pri0_rx_transitions",
        "pfc_pri1_rx_transitions",
        "pfc_pri2_rx_transitions",
        "pfc_pri3_rx_transitions",
        "pfc_pri4_rx_transitions",
        "pfc_pri5_rx_transitions",
        "pfc_pri6_rx_transitions",
        "pfc_pri7_rx_transitions",
        "tx_pause_frames",
        "tx_pfc_frames",
        "tx_pfc_ena_frames_pri0",
        "tx_pfc_ena_frames_pri1",
        "tx_pfc_ena_frames_pri2",
        "tx_pfc_ena_frames_pri3",
        "tx_pfc_ena_frames_pri4",
        "tx_pfc_ena_frames_pri5",
        "tx_pfc_ena_frames_pri6",
        "tx_pfc_ena_frames_pri7",
        "continuous_pause_events",
        "resume_pause_events",
        "continuous_roce_pause_events",
        "resume_roce_pause_events",
        "pfc_pri0_tx_transitions",
        "pfc_pri1_tx_transitions",
        "pfc_pri2_tx_transitions",
        "pfc_pri3_tx_transitions",
        "pfc_pri4_tx_transitions",
        "pfc_pri5_tx_transitions",
        "pfc_pri6_tx_transitions",
        "pfc_pri7_tx_transitions",
    ]


class Cx7EthtoolStatistics(BaseModel):
    """mlx (ConnectX-7) ethtool -S counters."""

    #: Regex matched against raw ``ethtool -S`` field names to identify per-queue
    queue_counter_regex: ClassVar[str] = r"^(rx|tx|ch)\d+"
    queue_error_regex: ClassVar[list[str]] = [
        r"xdp_drop",
        r"wqe_err",
        r"oversize_pkts_sw_drop",
        r"buff_alloc_err",
        r"arfs_err",
        r"tls_err",
        r"xdp_tx_err",
        r"dropped",
        r"cqe_err",
    ]
    queue_warning_regex: ClassVar[list[str]] = []

    rx_xdp_drop: Optional[int] = None
    rx_xdp_tx_err: Optional[int] = None
    tx_queue_dropped: Optional[int] = None
    tx_cqe_err: Optional[int] = None
    tx_xdp_err: Optional[int] = None
    rx_wqe_err: Optional[int] = None
    rx_oversize_pkts_sw_drop: Optional[int] = None
    rx_buff_alloc_err: Optional[int] = None
    rx_arfs_err: Optional[int] = None
    rx_tls_err: Optional[int] = None
    rx_xsk_xdp_drop: Optional[int] = None
    rx_xsk_wqe_err: Optional[int] = None
    rx_xsk_oversize_pkts_sw_drop: Optional[int] = None
    rx_xsk_buff_alloc_err: Optional[int] = None
    tx_xsk_err: Optional[int] = None
    rx_out_of_buffer: Optional[int] = None
    rx_if_down_packets: Optional[int] = None
    rx_steer_missed_packets: Optional[int] = None
    rx_oversize_pkts_buffer: Optional[int] = None
    rx_crc_errors_phy: Optional[int] = None
    rx_in_range_len_errors_phy: Optional[int] = None
    rx_out_of_range_len_phy: Optional[int] = None
    rx_oversize_pkts_phy: Optional[int] = None
    rx_symbol_err_phy: Optional[int] = None
    rx_unsupported_op_phy: Optional[int] = None
    rx_pause_ctrl_phy: Optional[int] = None
    tx_pause_ctrl_phy: Optional[int] = None
    rx_discards_phy: Optional[int] = None
    tx_discards_phy: Optional[int] = None
    tx_errors_phy: Optional[int] = None
    rx_undersize_pkts_phy: Optional[int] = None
    rx_fragments_phy: Optional[int] = None
    rx_jabbers_phy: Optional[int] = None
    link_down_events_phy: Optional[int] = None
    rx_pcs_symbol_err_phy: Optional[int] = None
    rx_pci_signal_integrity: Optional[int] = None
    tx_pci_signal_integrity: Optional[int] = None
    outbound_pci_stalled_rd: Optional[int] = None
    outbound_pci_stalled_wr: Optional[int] = None
    outbound_pci_stalled_rd_events: Optional[int] = None
    outbound_pci_stalled_wr_events: Optional[int] = None
    rx_prio0_discards: Optional[int] = None
    rx_prio1_discards: Optional[int] = None
    rx_prio2_discards: Optional[int] = None
    rx_prio3_discards: Optional[int] = None
    rx_prio4_discards: Optional[int] = None
    rx_prio5_discards: Optional[int] = None
    rx_prio6_discards: Optional[int] = None
    rx_prio7_discards: Optional[int] = None
    rx_global_pause: Optional[int] = None
    rx_prio0_pause: Optional[int] = None
    rx_prio1_pause: Optional[int] = None
    rx_prio2_pause: Optional[int] = None
    rx_prio3_pause: Optional[int] = None
    rx_prio4_pause: Optional[int] = None
    rx_prio5_pause: Optional[int] = None
    rx_prio6_pause: Optional[int] = None
    rx_prio7_pause: Optional[int] = None
    rx_global_pause_duration: Optional[int] = None
    rx_prio0_pause_duration: Optional[int] = None
    rx_prio1_pause_duration: Optional[int] = None
    rx_prio2_pause_duration: Optional[int] = None
    rx_prio3_pause_duration: Optional[int] = None
    rx_prio4_pause_duration: Optional[int] = None
    rx_prio5_pause_duration: Optional[int] = None
    rx_prio6_pause_duration: Optional[int] = None
    rx_prio7_pause_duration: Optional[int] = None
    tx_global_pause: Optional[int] = None
    tx_prio0_pause: Optional[int] = None
    tx_prio1_pause: Optional[int] = None
    tx_prio2_pause: Optional[int] = None
    tx_prio3_pause: Optional[int] = None
    tx_prio4_pause: Optional[int] = None
    tx_prio5_pause: Optional[int] = None
    tx_prio6_pause: Optional[int] = None
    tx_prio7_pause: Optional[int] = None
    tx_global_pause_duration: Optional[int] = None
    tx_prio0_pause_duration: Optional[int] = None
    tx_prio1_pause_duration: Optional[int] = None
    tx_prio2_pause_duration: Optional[int] = None
    tx_prio3_pause_duration: Optional[int] = None
    tx_prio4_pause_duration: Optional[int] = None
    tx_prio5_pause_duration: Optional[int] = None
    tx_prio6_pause_duration: Optional[int] = None
    tx_prio7_pause_duration: Optional[int] = None
    rx_global_pause_transition: Optional[int] = None
    rx_prio0_pause_transition: Optional[int] = None
    rx_prio1_pause_transition: Optional[int] = None
    rx_prio2_pause_transition: Optional[int] = None
    rx_prio3_pause_transition: Optional[int] = None
    rx_prio4_pause_transition: Optional[int] = None
    rx_prio5_pause_transition: Optional[int] = None
    rx_prio6_pause_transition: Optional[int] = None
    rx_prio7_pause_transition: Optional[int] = None
    tx_pause_storm_warning_events: Optional[int] = None
    tx_pause_storm_error_events: Optional[int] = None
    module_unplug: Optional[int] = None
    module_bus_stuck: Optional[int] = None
    module_high_temp: Optional[int] = None
    module_bad_shorted: Optional[int] = None
    ipsec_rx_drop_pkts: Optional[int] = None
    ipsec_rx_drop_bytes: Optional[int] = None
    ipsec_rx_drop_mismatch_sa_sel: Optional[int] = None
    ipsec_tx_drop_pkts: Optional[int] = None
    ipsec_tx_drop_bytes: Optional[int] = None
    ipsec_rx_drop_sp_alloc: Optional[int] = None
    ipsec_rx_drop_sadb_miss: Optional[int] = None
    ipsec_rx_drop_syndrome: Optional[int] = None
    ipsec_tx_drop_bundle: Optional[int] = None
    ipsec_tx_drop_no_state: Optional[int] = None
    ipsec_tx_drop_not_ip: Optional[int] = None
    ipsec_tx_drop_trailer: Optional[int] = None
    rx_prio0_buf_discard: Optional[int] = None
    rx_prio0_cong_discard: Optional[int] = None
    rx_prio1_buf_discard: Optional[int] = None
    rx_prio1_cong_discard: Optional[int] = None
    rx_prio2_buf_discard: Optional[int] = None
    rx_prio2_cong_discard: Optional[int] = None
    rx_prio3_buf_discard: Optional[int] = None
    rx_prio3_cong_discard: Optional[int] = None
    rx_prio4_buf_discard: Optional[int] = None
    rx_prio4_cong_discard: Optional[int] = None
    rx_prio5_buf_discard: Optional[int] = None
    rx_prio5_cong_discard: Optional[int] = None
    rx_prio6_buf_discard: Optional[int] = None
    rx_prio6_cong_discard: Optional[int] = None
    rx_prio7_buf_discard: Optional[int] = None
    rx_prio7_cong_discard: Optional[int] = None

    error_fields: ClassVar[list[str]] = [
        "rx_xdp_drop",
        "rx_xdp_tx_err",
        "tx_queue_dropped",
        "tx_cqe_err",
        "tx_xdp_err",
        "rx_wqe_err",
        "rx_oversize_pkts_sw_drop",
        "rx_buff_alloc_err",
        "rx_arfs_err",
        "rx_tls_err",
        "rx_xsk_xdp_drop",
        "rx_xsk_wqe_err",
        "rx_xsk_oversize_pkts_sw_drop",
        "rx_xsk_buff_alloc_err",
        "tx_xsk_err",
        "rx_out_of_buffer",
        "rx_if_down_packets",
        "rx_steer_missed_packets",
        "rx_oversize_pkts_buffer",
        "rx_crc_errors_phy",
        "rx_in_range_len_errors_phy",
        "rx_out_of_range_len_phy",
        "rx_oversize_pkts_phy",
        "rx_symbol_err_phy",
        "rx_unsupported_op_phy",
        "rx_discards_phy",
        "tx_discards_phy",
        "tx_errors_phy",
        "rx_undersize_pkts_phy",
        "rx_fragments_phy",
        "rx_jabbers_phy",
        "link_down_events_phy",
        "rx_pcs_symbol_err_phy",
        "rx_pci_signal_integrity",
        "tx_pci_signal_integrity",
        "outbound_pci_stalled_rd",
        "outbound_pci_stalled_wr",
        "outbound_pci_stalled_rd_events",
        "outbound_pci_stalled_wr_events",
        "rx_prio0_discards",
        "rx_prio1_discards",
        "rx_prio2_discards",
        "rx_prio3_discards",
        "rx_prio4_discards",
        "rx_prio5_discards",
        "rx_prio6_discards",
        "rx_prio7_discards",
        "tx_pause_storm_warning_events",
        "tx_pause_storm_error_events",
        "module_unplug",
        "module_bus_stuck",
        "module_high_temp",
        "module_bad_shorted",
        "ipsec_rx_drop_pkts",
        "ipsec_rx_drop_bytes",
        "ipsec_rx_drop_mismatch_sa_sel",
        "ipsec_tx_drop_pkts",
        "ipsec_tx_drop_bytes",
        "ipsec_rx_drop_sp_alloc",
        "ipsec_rx_drop_sadb_miss",
        "ipsec_rx_drop_syndrome",
        "ipsec_tx_drop_bundle",
        "ipsec_tx_drop_no_state",
        "ipsec_tx_drop_not_ip",
        "ipsec_tx_drop_trailer",
        "rx_prio0_buf_discard",
        "rx_prio0_cong_discard",
        "rx_prio1_buf_discard",
        "rx_prio1_cong_discard",
        "rx_prio2_buf_discard",
        "rx_prio2_cong_discard",
        "rx_prio3_buf_discard",
        "rx_prio3_cong_discard",
        "rx_prio4_buf_discard",
        "rx_prio4_cong_discard",
        "rx_prio5_buf_discard",
        "rx_prio5_cong_discard",
        "rx_prio6_buf_discard",
        "rx_prio6_cong_discard",
        "rx_prio7_buf_discard",
        "rx_prio7_cong_discard",
    ]

    warning_fields: ClassVar[list[str]] = [
        "rx_pause_ctrl_phy",
        "rx_global_pause",
        "rx_prio0_pause",
        "rx_prio1_pause",
        "rx_prio2_pause",
        "rx_prio3_pause",
        "rx_prio4_pause",
        "rx_prio5_pause",
        "rx_prio6_pause",
        "rx_prio7_pause",
        "rx_global_pause_transition",
        "rx_prio0_pause_transition",
        "rx_prio1_pause_transition",
        "rx_prio2_pause_transition",
        "rx_prio3_pause_transition",
        "rx_prio4_pause_transition",
        "rx_prio5_pause_transition",
        "rx_prio6_pause_transition",
        "rx_prio7_pause_transition",
        "rx_global_pause_duration",
        "rx_prio0_pause_duration",
        "rx_prio1_pause_duration",
        "rx_prio2_pause_duration",
        "rx_prio3_pause_duration",
        "rx_prio4_pause_duration",
        "rx_prio5_pause_duration",
        "rx_prio6_pause_duration",
        "rx_prio7_pause_duration",
        "tx_pause_ctrl_phy",
        "tx_global_pause",
        "tx_prio0_pause",
        "tx_prio1_pause",
        "tx_prio2_pause",
        "tx_prio3_pause",
        "tx_prio4_pause",
        "tx_prio5_pause",
        "tx_prio6_pause",
        "tx_prio7_pause",
        "tx_global_pause_duration",
        "tx_prio0_pause_duration",
        "tx_prio1_pause_duration",
        "tx_prio2_pause_duration",
        "tx_prio3_pause_duration",
        "tx_prio4_pause_duration",
        "tx_prio5_pause_duration",
        "tx_prio6_pause_duration",
        "tx_prio7_pause_duration",
    ]


VendorEthtoolStatisticsModel = Union[
    PollaraEthtoolStatistics,
    Thor2EthtoolStatistics,
    Cx7EthtoolStatistics,
]


VendorEthtoolStatisticsCls = type[VendorEthtoolStatisticsModel]


# Map kernel driver name prefixes (from `ethtool -i`) to vendor-specific models
# ionic -> Pollara, bnxt  -> Thor2, mlx   -> ConnectX-7
VENDOR_PREFIX_MAP: dict[str, VendorEthtoolStatisticsCls] = {
    "ionic": PollaraEthtoolStatistics,
    "bnxt": Thor2EthtoolStatistics,
    "mlx": Cx7EthtoolStatistics,
}


def extract_queue_counters(stats: dict[str, str], queue_counter_regex: str) -> dict[str, int]:
    """Extract per-queue counters from a raw ``ethtool -S`` stats dict.

    Devices can report hundreds of per-queue counters. These are matched by the
    vendor's ``queue_counter_regex`` and retained (rather than dropped like other
    non-enumerated fields) so they remain available in the data model for error
    detection.

    Args:
        stats: Mapping of raw ``ethtool -S`` field name -> string value.
        queue_counter_regex: Vendor regex matched against field names to identify
            per-queue counters.

    Returns:
        Mapping of matching field name -> integer value. The ``netdev`` marker key
        and non-integer values are skipped.
    """
    pattern = re.compile(queue_counter_regex)
    queue_counters: dict[str, int] = {}
    for name, value in stats.items():
        if name == "netdev" or not pattern.match(name):
            continue
        try:
            queue_counters[name] = int(value)
        except (TypeError, ValueError):
            continue
    return queue_counters


class EthtoolStatistics(BaseModel):
    """Per-netdev ethtool -S row with optional vendor-parsed counters."""

    netdev: Optional[str] = None
    driver: Optional[str] = Field(
        default=None,
        description="Kernel driver (from 'ethtool -i') used for vendor model selection",
    )
    vendor_statistics: Optional[VendorEthtoolStatisticsModel] = None
    queue_statistics: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "High-cardinality per-queue ethtool -S counters (raw field name -> value) "
            "captured via the vendor queue_counter_regex for error detection"
        ),
    )

    @model_validator(mode="after")
    def validate_atleast_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be set in EthtoolStatistics")
        return self
