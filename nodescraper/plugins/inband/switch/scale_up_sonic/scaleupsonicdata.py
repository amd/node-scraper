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

from typing import ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from nodescraper.models import DataModel


class SonicInterfaceStatus(BaseModel):
    """Per-port info from ``show interface status``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: Optional[str] = None
    lanes: Optional[str] = None
    speed: Optional[str] = None
    mtu: Optional[int] = None
    fec: Optional[str] = None
    alias: Optional[str] = None
    vlan: Optional[str] = None
    oper: Optional[str] = None
    admin: Optional[str] = None
    type: Optional[str] = None
    asym_pfc: Optional[str] = None

    error_fields: ClassVar[dict[str, List[str]]] = {
        "oper": ["up"],
    }


class SonicFecStatus(BaseModel):
    """Per-port FEC status from ``show interface fec status``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    oper: Optional[str] = None
    admin: Optional[str] = None


class SonicInterfaceCounters(BaseModel):
    """Per-port summary counters from ``show interface counters``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    state: Optional[str] = None
    rx_ok: Optional[int] = None
    rx_bps: Optional[str] = None
    rx_util: Optional[str] = None
    rx_err: Optional[int] = None
    rx_drp: Optional[int] = None
    rx_ovr: Optional[int] = None
    tx_ok: Optional[int] = None
    tx_bps: Optional[str] = None
    tx_util: Optional[str] = None
    tx_err: Optional[int] = None
    tx_drp: Optional[int] = None
    tx_ovr: Optional[int] = None

    error_fields: ClassVar[dict[str, List[str]]] = {
        "state": ["U"],
        "rx_err": ["0"],
        "rx_ovr": ["0"],
        "tx_err": ["0"],
        "tx_ovr": ["0"],
    }

    warning_fields: ClassVar[dict[str, List[str]]] = {
        "rx_drp": ["0"],
        "tx_drp": ["0"],
    }


class SonicQueueCounter(BaseModel):
    """Single queue counter entry from ``show queue counters``"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    txq: Optional[str] = None
    counter_pkts: Optional[int] = None
    counter_bytes: Optional[int] = None
    drop_pkts: Optional[int] = None
    drop_bytes: Optional[int] = None

    warning_fields: ClassVar[dict[str, List[str]]] = {
        "drop_pkts": ["0"],
        "drop_bytes": ["0"],
    }


class SonicPortData(BaseModel):
    """All collected per-port data for a SONiC switch"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    interface_status: Optional[SonicInterfaceStatus] = None
    interface_counters: Optional[SonicInterfaceCounters] = None
    fec_status: Optional[SonicFecStatus] = None
    queue_counters: Optional[List[SonicQueueCounter]] = None


class ScaleUpSonicDataModel(DataModel):
    """Collected output of SONiC switch commands"""

    port_list: Optional[List[str]] = None

    port: Optional[Dict[str, SonicPortData]] = None
