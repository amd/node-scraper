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
from __future__ import annotations

import json

import pytest
from framework.common.serviceability_dummy_data import dummy_helios_sensor_log_entry

from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataLoadError,
    ServiceabilityDataModel,
)


def test_import_model_from_redfish_entries_collection():
    member = dummy_helios_sensor_log_entry()
    payload = {
        "@odata.id": "/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries",
        "Members": [member, {"Message": "no afid"}],
    }
    model = ServiceabilityDataModel.import_model(payload)
    assert len(model.rf_events) == 2
    assert model.responses[payload["@odata.id"]]["Members"] == payload["Members"]


def test_import_model_from_redfish_entries_file(tmp_path):
    member = dummy_helios_sensor_log_entry()
    path = tmp_path / "entries.json"
    path.write_text(
        json.dumps(
            {
                "@odata.id": "/redfish/v1/Systems/Instinct_Accelerators/LogServices/EventLog/Entries",
                "Members": [member],
            }
        ),
        encoding="utf-8",
    )
    model = ServiceabilityDataModel.import_model(str(path))
    assert len(model.rf_events) == 1
    assert model.rf_events[0]["Id"] == member["Id"]


def test_import_model_missing_file():
    with pytest.raises(ServiceabilityDataLoadError, match="not found"):
        ServiceabilityDataModel.import_model("/tmp/does-not-exist-serviceability-data.json")
