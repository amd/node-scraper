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
from nodescraper.connection.redfish.redfish_manager import MultiTargetRedfishConnection
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.plugins.ooband.redfish_inventory.analyzer_args import (
    RedfishInventoryAnalyzerArgs,
)
from nodescraper.plugins.ooband.redfish_inventory.firmware_compare import (
    firmware_components,
)
from nodescraper.plugins.ooband.redfish_inventory.inventory_analyzer import (
    RedfishInventoryAnalyzer,
)
from nodescraper.plugins.ooband.redfish_inventory.inventory_data import (
    RedfishInventoryDataModel,
)
from nodescraper.plugins.ooband.redfish_inventory.inventory_plugin import (
    RedfishInventoryPlugin,
)

FW_COLLECTION = "/redfish/v1/UpdateService/FirmwareInventory"
FW_ACTIVE = "/redfish/v1/UpdateService/FirmwareInventory/fw-active"
FW_SLOT_A = "/redfish/v1/UpdateService/FirmwareInventory/fw-slot-0001"
FW_SLOT_B = "/redfish/v1/UpdateService/FirmwareInventory/fw-slot-0002"
TARGET_A = "node-a"
TARGET_B = "node-b"


def _member(path: str, fw_id: str, version, **extra) -> dict:
    body = {
        "@odata.id": path,
        "Id": fw_id,
        "Version": version,
        "Status": {"Health": "OK", "State": "Enabled"},
        "SoftwareId": "SW-1",
        "Updateable": True,
        "Oem": {"SVN": "4"},
    }
    body.update(extra)
    return body


def _model(*pairs: tuple[str, dict]) -> RedfishInventoryDataModel:
    return RedfishInventoryDataModel(responses={path: body for path, body in pairs})


def test_null_version_is_recorded_with_the_other_firmware_fields():
    model = _model(
        (
            FW_ACTIVE,
            _member(FW_ACTIVE, "fw-active", None, SoftwareId=None, Updateable=False, Oem={}),
        ),
        (
            FW_COLLECTION,
            {"@odata.id": FW_COLLECTION, "Members": [{"@odata.id": FW_ACTIVE}]},
        ),
    )
    components = firmware_components(model)
    assert list(components) == ["fw-active"]
    assert components["fw-active"] == {
        "version": "N/A",
        "health": "OK",
        "state": "Enabled",
        "software_id": "N/A",
        "updateable": "False",
        "svn": "",
    }


def test_instance_suffixes_stay_separate_ids():
    model = _model(
        (FW_SLOT_A, _member(FW_SLOT_A, "fw-slot-0001", "1.0")),
        (FW_SLOT_B, _member(FW_SLOT_B, "fw-slot-0002", "1.0")),
    )
    assert set(firmware_components(model)) == {"fw-slot-0001", "fw-slot-0002"}


def test_version_mismatch_warns_and_includes_firmware_fields(system_info):
    analyzer = RedfishInventoryAnalyzer(system_info=system_info)
    result = analyzer.compare_firmware(
        {
            TARGET_A: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", "1.0"))),
            TARGET_B: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", "1.1", Oem={"SVN": "9"}))),
        }
    )
    assert result.status == ExecutionStatus.WARNING
    assert result.message.startswith("Firmware differs for 1 component(s)")
    assert len(result.events) == 1
    event = result.events[0]
    assert event.category == EventCategory.FW.value
    assert event.priority == EventPriority.WARNING
    assert "node-a=version=1.0 health=OK state=Enabled software_id=SW-1 updateable=True svn=4" in (
        event.description
    )
    assert "node-b=version=1.1 health=OK state=Enabled software_id=SW-1 updateable=True svn=9" in (
        event.description
    )


def test_missing_member_warns(system_info):
    analyzer = RedfishInventoryAnalyzer(system_info=system_info)
    result = analyzer.compare_firmware(
        {
            TARGET_A: _model((FW_SLOT_A, _member(FW_SLOT_A, "fw-slot-0001", "1.0"))),
            TARGET_B: _model((FW_SLOT_B, _member(FW_SLOT_B, "fw-slot-0002", "1.0"))),
        }
    )
    assert result.status == ExecutionStatus.WARNING
    ids = {event.data["firmware_id"] for event in result.events}
    assert ids == {"fw-slot-0001", "fw-slot-0002"}
    missing = next(event for event in result.events if event.data["firmware_id"] == "fw-slot-0001")
    assert "node-b=missing" in missing.description


def test_matching_versions_are_ok(system_info):
    member = _member(FW_ACTIVE, "fw-active", "1.0")
    analyzer = RedfishInventoryAnalyzer(system_info=system_info)
    result = analyzer.compare_firmware(
        {
            TARGET_A: _model((FW_ACTIVE, member)),
            TARGET_B: _model((FW_ACTIVE, dict(member))),
        }
    )
    assert result.status == ExecutionStatus.OK
    assert result.events == []
    assert result.message.startswith("Firmware versions match across 2 targets")


def test_compare_firmware_can_be_turned_off(system_info):
    analyzer = RedfishInventoryAnalyzer(system_info=system_info)
    result = analyzer.compare_firmware(
        {
            TARGET_A: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", "1.0"))),
            TARGET_B: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", "9.0"))),
        },
        RedfishInventoryAnalyzerArgs(compare_firmware=False),
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == "Firmware comparison disabled"
    assert result.events == []


def test_no_firmware_members_warns_once(system_info):
    analyzer = RedfishInventoryAnalyzer(system_info=system_info)
    result = analyzer.compare_firmware(
        {
            TARGET_A: RedfishInventoryDataModel(responses={}),
            TARGET_B: RedfishInventoryDataModel(responses={}),
        }
    )
    assert result.status == ExecutionStatus.WARNING
    assert len(result.events) == 1
    assert result.events[0].description == (
        "Firmware comparison did not run: no FirmwareInventory members were collected"
    )


def test_plugin_compares_multi_target_inventory(system_info):
    connection = MultiTargetRedfishConnection({})
    connection.multi_target_data = {
        TARGET_A: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", None))),
        TARGET_B: _model((FW_ACTIVE, _member(FW_ACTIVE, "fw-active", "2.0"))),
    }

    class _Manager:
        def __init__(self, open_connection):
            self.connection = open_connection

    plugin = RedfishInventoryPlugin(
        system_info=system_info, connection_manager=_Manager(connection)
    )
    result = plugin.analyze()
    assert result.status == ExecutionStatus.WARNING
    assert "version=N/A" in result.events[0].description
    assert "version=2.0" in result.events[0].description
