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

from nodescraper.plugins.serviceability.mi3xx.mi3xx_cper_utils import (
    RF_CPER_AFID_MIN,
    event_aca_includes_serial,
    event_afids_from_oem,
    event_has_aca_decode,
    should_skip_cper_fetch_or_decode,
)

_DUMMY_META_SERIAL = "DUMMY-GPU-SERIAL-0001"
_DUMMY_DECODED_FIELD = "dummy_error_type"


def _oem_err_row(*, serial: bool = True, decoded: bool = True):
    meta = {"SerialNumber": _DUMMY_META_SERIAL} if serial else {"GpuFw": "dummy-fw"}
    dec = {"error_type": _DUMMY_DECODED_FIELD} if decoded else {}
    return {"DecodedData": dec, "MetaData": meta}


def test_skip_when_afids_below_threshold_and_aca_has_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": 22}],
            "ErrDataArr": [_oem_err_row()],
        }
    }
    assert event_afids_from_oem(event) == [22]
    assert should_skip_cper_fetch_or_decode(event) is True


def test_no_skip_when_rf_range_afid_even_with_aca_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": RF_CPER_AFID_MIN}],
            "ErrDataArr": [_oem_err_row()],
        }
    }
    assert should_skip_cper_fetch_or_decode(event) is False


def test_skip_when_aca_decode_without_serial():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": RF_CPER_AFID_MIN}],
            "ErrDataArr": [_oem_err_row(serial=False)],
        }
    }
    assert event_has_aca_decode(event) is True
    assert event_aca_includes_serial(event) is False
    assert should_skip_cper_fetch_or_decode(event) is True


def test_no_skip_when_no_err_data_decoded():
    event = {
        "Oem": {
            "AMDFieldIdentifiers": [{"AFID": 22}],
        }
    }
    assert should_skip_cper_fetch_or_decode(event) is False


def test_no_skip_when_aca_serial_but_no_afid_list():
    event = {
        "Oem": {
            "ErrDataArr": [_oem_err_row()],
        }
    }
    assert event_afids_from_oem(event) == []
    assert should_skip_cper_fetch_or_decode(event) is False


@pytest.mark.parametrize(
    "afids,expect_skip",
    [
        ([22, 28], True),
        ([22, RF_CPER_AFID_MIN], False),
    ],
)
def test_skip_requires_all_afids_below_rf_threshold(afids, expect_skip):
    identifiers = [{"AFID": a} for a in afids]
    event = {"Oem": {"AMDFieldIdentifiers": identifiers, "ErrDataArr": [_oem_err_row()]}}
    assert should_skip_cper_fetch_or_decode(event) is expect_skip
