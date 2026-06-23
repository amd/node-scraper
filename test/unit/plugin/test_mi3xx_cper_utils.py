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
import pytest
from serviceability_dummy_data import (
    DUMMY_AFID_BELOW_RF,
    DUMMY_AFID_FATAL_HBM,
    DUMMY_RF_CPER_AFID,
    dummy_aca_err_row,
)

from nodescraper.plugins.serviceability.mi3xx.mi3xx_cper_utils import (
    CPER_METHOD_AFID_MAX,
    event_aca_includes_serial,
    event_afids_from_oem,
    event_has_aca_decode,
    is_cper_method_afid,
    is_redfish_method_afid,
    should_skip_cper_fetch_or_decode,
)


def test_skip_when_afids_below_threshold_and_aca_has_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_AFID_BELOW_RF}],
            "ErrDataArr": [dummy_aca_err_row()],
        }
    }
    assert event_afids_from_oem(event) == [DUMMY_AFID_BELOW_RF]
    assert should_skip_cper_fetch_or_decode(event) is True


def test_event_afids_from_oem_nested_amd_block():
    event = {
        "Oem": {
            "AMD": {
                "AMDFieldIdentifiers": [{"AFID": DUMMY_AFID_BELOW_RF}],
                "ErrDataArr": [dummy_aca_err_row()],
            }
        }
    }
    assert event_afids_from_oem(event) == [DUMMY_AFID_BELOW_RF]
    assert event_has_aca_decode(event) is True
    assert should_skip_cper_fetch_or_decode(event) is True


def test_err_data_arr_entries_nested_amd_block():
    event = {"Oem": {"AMD": {"ErrDataArr": [dummy_aca_err_row()]}}}
    assert event_has_aca_decode(event) is True
    assert event_aca_includes_serial(event) is True


def test_afid_method_ranges():
    assert is_cper_method_afid(DUMMY_AFID_BELOW_RF)
    assert is_cper_method_afid(CPER_METHOD_AFID_MAX)
    assert not is_cper_method_afid(CPER_METHOD_AFID_MAX + 1)
    assert is_redfish_method_afid(DUMMY_RF_CPER_AFID)
    assert not is_redfish_method_afid(DUMMY_AFID_BELOW_RF)


def test_no_skip_when_rf_range_afid_even_with_aca_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_RF_CPER_AFID}],
            "ErrDataArr": [dummy_aca_err_row()],
        }
    }
    assert should_skip_cper_fetch_or_decode(event) is False


def test_skip_when_aca_decode_without_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_RF_CPER_AFID}],
            "ErrDataArr": [dummy_aca_err_row(serial=False)],
        }
    }
    assert event_has_aca_decode(event) is True
    assert event_aca_includes_serial(event) is False
    assert should_skip_cper_fetch_or_decode(event) is True


def test_no_skip_when_no_err_data_decoded():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": DUMMY_AFID_BELOW_RF}],
        }
    }
    assert should_skip_cper_fetch_or_decode(event) is False


def test_no_skip_when_aca_serial_but_no_afid_list():
    event = {
        "Oem": {
            "ErrDataArr": [dummy_aca_err_row()],
        }
    }
    assert event_afids_from_oem(event) == []
    assert should_skip_cper_fetch_or_decode(event) is False


@pytest.mark.parametrize(
    "afids,expect_skip",
    [
        ([DUMMY_AFID_BELOW_RF, DUMMY_AFID_FATAL_HBM], True),
        ([DUMMY_AFID_BELOW_RF, DUMMY_RF_CPER_AFID], False),
    ],
)
def test_skip_requires_all_afids_cper_method(afids, expect_skip):
    identifiers = [{"AFID": a} for a in afids]
    event = {"Oem": {"AMDFieldIdentifiers": identifiers, "ErrDataArr": [dummy_aca_err_row()]}}
    assert should_skip_cper_fetch_or_decode(event) is expect_skip
