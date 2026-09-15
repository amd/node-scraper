###############################################################################
#
# MIT License
#
###############################################################################
from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.inband.nic.analyzer_args import NicAnalyzerArgs
from nodescraper.plugins.inband.nic.nic_analyzer import NicAnalyzer
from nodescraper.plugins.inband.nic.nic_data import (
    NicCliDevice,
    NicDataModel,
    PensandoNicVersionFirmware,
)


def test_broadcom_firmware_exact_match(system_info):
    analyzer = NicAnalyzer(system_info)
    data = NicDataModel(
        broadcom_nic_devices=[NicCliDevice(device_num=0, model="Thor2")],
        broadcom_nic_firmware={0: "238.1.169.0"},
    )

    result = analyzer.analyze_data(
        data,
        NicAnalyzerArgs(expected_nic_firmware="238.1.169.0"),
    )

    assert result.status == ExecutionStatus.OK
    assert not result.events


def test_broadcom_firmware_mismatch_is_reported(system_info):
    analyzer = NicAnalyzer(system_info)
    data = NicDataModel(
        broadcom_nic_devices=[NicCliDevice(device_num=0, model="Thor2")],
        broadcom_nic_firmware={0: "238.1.168.0"},
    )

    result = analyzer.analyze_data(
        data,
        NicAnalyzerArgs(expected_nic_firmware="238.1.169.0"),
    )

    assert result.status == ExecutionStatus.WARNING
    assert any("firmware" in event.description.lower() for event in result.events)


def test_missing_broadcom_firmware_is_reported(system_info):
    analyzer = NicAnalyzer(system_info)
    data = NicDataModel(
        broadcom_nic_devices=[NicCliDevice(device_num=0, model="Thor2")],
    )

    result = analyzer.analyze_data(
        data,
        NicAnalyzerArgs(expected_nic_firmware="238.1.169.0"),
    )

    assert result.status == ExecutionStatus.WARNING
    assert any("unavailable" in event.data["reason"] for event in result.events)


def test_pensando_firmware_is_validated_by_nic_analyzer(system_info):
    analyzer = NicAnalyzer(system_info)
    data = NicDataModel(
        pensando_nic_version_firmware=[
            PensandoNicVersionFirmware(
                nic_id="card0",
                pcie_bdf="0000:01:00.0",
                firmware_a="238.1.169.0",
            )
        ]
    )
    args = NicAnalyzerArgs(expected_nic_firmware="238.1.169.0")

    result = analyzer.analyze_data(data, args)

    assert result.status == ExecutionStatus.OK
    assert not result.events
