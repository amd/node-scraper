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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums import EventPriority
from nodescraper.plugins.inband.pcie.analyzer_args import PcieAnalyzerArgs
from nodescraper.plugins.inband.pcie.pcie_analyzer import PcieAnalyzer
from nodescraper.plugins.inband.pcie.pcie_data import (
    CapabilityEnum,
    ECapAer,
    ECapSecpci,
    ExtendedCapabilityEnum,
    PcieCfgSpace,
    PcieDataModel,
    PcieDeviceSnapshot,
    PcieExp,
    PcieInventory,
    PcieInventoryDevice,
    build_pcie_device_snapshot,
    build_pcie_snapshots,
)
from nodescraper.plugins.inband.pcie.pcie_inventory import parse_lspci_inventory
from nodescraper.plugins.inband.pcie.pcie_plugin import PciePlugin

SAMPLE_LSPCI_OUTPUT = """\
0000:00:01.0 PCI bridge: Example Host Bridge [8086:1111] (rev 04)
\tSubsystem: Example Corp Example Bridge [8086:0000]
\tControl: I/O+ Mem+ BusMaster+
\tStatus: Cap+ 66MHz-
\tLnkSta:\tSpeed 8GT/s (ok), Width x16 (ok)
0000:03:00.0 Ethernet controller: Example Corp Example NIC [8086:2222] (rev 01)
\tSubsystem: Example Corp Example NIC Subsystem [8086:0001]
\tControl: I/O+ Mem+ BusMaster+
\tStatus: Cap+ 66MHz-
\tKernel driver in use: example_nic
\tLnkSta:\tSpeed 5GT/s (ok), Width x4 (ok)
"""


@pytest.fixture
def sample_inventory():
    return parse_lspci_inventory(SAMPLE_LSPCI_OUTPUT)


def test_parse_lspci_inventory_total_count(sample_inventory):
    assert sample_inventory.total_count == 2


def test_parse_lspci_inventory_device_fields(sample_inventory):
    device = sample_inventory.devices["0000:03:00.0"]
    assert device.vendor == "8086"
    assert device.device == "2222"
    assert device.driver == "example_nic"
    assert device.speed == "5GT/s"
    assert device.width == "x4"
    assert device.link_training == "ok"


def test_get_compare_snapshot_full_bom(sample_inventory):
    model = PcieDataModel(inventory=sample_inventory, pcie_cfg_space={})
    snapshot = model.get_compare_snapshot("full_bom")
    assert snapshot["inventory"]["total_count"] == 2
    nic = snapshot["inventory"]["devices"]["0000:03:00.0"]
    assert nic["vendor"] == "8086"
    assert nic["driver"] == "example_nic"
    assert "lnkctl" not in nic


def test_get_compare_snapshot_pcie_link(sample_inventory):
    model = PcieDataModel(inventory=sample_inventory, pcie_cfg_space={})
    snapshot = model.get_compare_snapshot("pcie_link")
    nic = snapshot["inventory"]["devices"]["0000:03:00.0"]
    assert "driver" not in nic
    assert nic["speed"] == "5GT/s"


def test_check_inventory_expected_match(system_info):
    inventory = PcieInventory(
        total_count=1,
        devices={
            "0000:03:00.0": PcieInventoryDevice(
                address="0000:03:00.0",
                vendor="8086",
                device="2222",
                driver="example_nic",
                speed="5GT/s",
                width="x4",
            )
        },
    )
    analyzer = PcieAnalyzer(system_info=system_info, logger=MagicMock())
    analyzer.result.events = []
    args = PcieAnalyzerArgs(
        expected_total_count=1,
        expected_devices={
            "0000:03:00.0": {
                "vendor": "8086",
                "driver": "example_nic",
            }
        },
        fail_on_extra_devices=True,
    )
    analyzer.check_inventory_expected(
        PcieDataModel(inventory=inventory, pcie_cfg_space={}),
        args,
    )
    assert analyzer.result.events == []


def test_check_inventory_expected_mismatch(system_info):
    inventory = PcieInventory(
        total_count=1,
        devices={
            "0000:03:00.0": PcieInventoryDevice(
                address="0000:03:00.0",
                vendor="8086",
                device="2222",
            )
        },
    )
    analyzer = PcieAnalyzer(system_info=system_info, logger=MagicMock())
    analyzer.result.events = []
    args = PcieAnalyzerArgs(
        expected_devices={"0000:03:00.0": {"driver": "other_driver"}},
    )
    analyzer.check_inventory_expected(
        PcieDataModel(inventory=inventory, pcie_cfg_space={}),
        args,
    )
    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.ERROR


def test_check_inventory_extra_device(system_info):
    inventory = PcieInventory(
        total_count=2,
        devices={
            "0000:03:00.0": PcieInventoryDevice(address="0000:03:00.0", vendor="8086"),
            "0000:04:00.0": PcieInventoryDevice(address="0000:04:00.0", vendor="8086"),
        },
    )
    analyzer = PcieAnalyzer(system_info=system_info, logger=MagicMock())
    analyzer.result.events = []
    args = PcieAnalyzerArgs(
        expected_devices={"0000:03:00.0": {"vendor": "8086"}},
        fail_on_extra_devices=True,
    )
    analyzer.check_inventory_expected(
        PcieDataModel(inventory=inventory, pcie_cfg_space={}),
        args,
    )
    assert any("Unexpected PCI devices" in event.description for event in analyzer.result.events)


def test_pcie_plugin_load_run_data_uses_inventory_snapshot(tmp_path, sample_inventory):
    model = PcieDataModel(inventory=sample_inventory, pcie_cfg_space={})
    model_path = tmp_path / "pciedatamodel.json"
    model_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    snapshot = PciePlugin.load_run_data(str(model_path))
    assert snapshot is not None
    assert "pcie_cfg_space" not in snapshot
    assert snapshot["inventory"]["total_count"] == 2


def test_pcie_analyzer_args_defaults():
    args = PcieAnalyzerArgs()
    assert args.profile == "full_bom"
    assert args.fail_on_extra_devices is True
    assert args.expected_devices == {}
    assert args.exp_sriov_count is None
    assert args.expected_pcie_snapshot is None


def _dummy_cfg_space(
    err_cor_src_id: int = 0x0019,
    lane_err_stat: int = 0,
    lnk_ctl2_drs: int = 1,
) -> PcieCfgSpace:
    pcie_exp = PcieExp()
    pcie_exp.lnk_ctl_2_reg.val = lnk_ctl2_drs << 14
    ecap_aer = ECapAer()
    ecap_aer.err_src_id.val = err_cor_src_id
    ecap_sec_pci = ECapSecpci()
    ecap_sec_pci.lane_err_stat.val = lane_err_stat
    return PcieCfgSpace(
        cap_structure={CapabilityEnum.PCIE_EXP: pcie_exp},
        ecap_structure={
            ExtendedCapabilityEnum.AER: ecap_aer,
            ExtendedCapabilityEnum.SPCI: ecap_sec_pci,
        },
    )


def test_build_pcie_device_snapshot_extracts_register_fields():
    cfg = _dummy_cfg_space(err_cor_src_id=0x0019, lnk_ctl2_drs=1, lane_err_stat=0x200)
    snapshot = build_pcie_device_snapshot(cfg)
    assert snapshot.err_cor_src_id == 0x0019
    assert snapshot.lnk_ctl2_drs == 1
    assert snapshot.lane_err_stat == 0x200


def test_pcie_analyzer_args_build_from_model(sample_inventory):
    cfg = _dummy_cfg_space()
    model = PcieDataModel(
        inventory=sample_inventory,
        pcie_cfg_space={"0000:aa:00.0": cfg},
        pcie_snapshot=build_pcie_snapshots({"0000:aa:00.0": cfg}),
    )
    args = PcieAnalyzerArgs.build_from_model(model)
    assert args.expected_total_count == 2
    assert "0000:03:00.0" in args.expected_devices
    assert args.expected_pcie_snapshot is not None


def test_get_compare_snapshot_includes_pcie_snapshot(sample_inventory):
    cfg = _dummy_cfg_space()
    model = PcieDataModel(
        inventory=sample_inventory,
        pcie_cfg_space={"0000:aa:00.0": cfg},
        pcie_snapshot=build_pcie_snapshots({"0000:aa:00.0": cfg}),
    )
    snapshot = model.get_compare_snapshot("full_bom")
    assert snapshot["pcie_snapshot"]["0000:aa:00.0"]["err_cor_src_id"] == "0x19"


def test_expected_pcie_snapshot_mismatch(system_info):
    analyzer = PcieAnalyzer(system_info=system_info, logger=MagicMock())
    analyzer.result.events = []
    pcie_data = PcieDataModel(
        pcie_cfg_space={},
        pcie_snapshot={"0000:aa:00.0": PcieDeviceSnapshot(lane_err_stat=0x200)},
    )
    args = PcieAnalyzerArgs(
        expected_pcie_snapshot={"0000:aa:00.0": PcieDeviceSnapshot(lane_err_stat=0)},
    )
    analyzer.check_expected_pcie_snapshot(pcie_data=pcie_data, args=args)
    assert any(
        e.description == "PCIe register snapshot field mismatch"
        and e.data.get("field") == "lane_err_stat"
        and e.priority == EventPriority.ERROR
        for e in analyzer.result.events
    )


def test_expected_pcie_snapshot_match(system_info):
    analyzer = PcieAnalyzer(system_info=system_info, logger=MagicMock())
    analyzer.result.events = []
    pcie_data = PcieDataModel(
        pcie_cfg_space={},
        pcie_snapshot={"0000:aa:00.0": PcieDeviceSnapshot(err_cor_src_id=0x0019)},
    )
    args = PcieAnalyzerArgs(
        expected_pcie_snapshot={"0000:aa:00.0": PcieDeviceSnapshot(err_cor_src_id=0x0019)},
    )
    analyzer.check_expected_pcie_snapshot(pcie_data=pcie_data, args=args)
    assert not analyzer.result.events
