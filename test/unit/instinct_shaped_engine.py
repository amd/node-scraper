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

from typing import Any, Optional

__all__ = ["InstinctShapedEngine"]

_LAST_CALL: dict[str, Any] = {}


def clear_last_call() -> None:
    _LAST_CALL.clear()


def get_last_call() -> dict[str, Any]:
    return dict(_LAST_CALL)


class InstinctShapedEngine:
    """Mirrors keyword parameters of ``InstinctServiceAssistant.get_service_info``."""

    def __init__(self, afid_sag: str) -> None:
        self.afid_sag = afid_sag

    def get_service_info(
        self,
        rf_events: list[Any],
        from_ac_cycle: int = -1,
        from_date: Optional[str] = None,
        cper_data: Optional[dict[str, Any]] = None,
        designation_serials: Optional[dict[str, str]] = None,
        suppress_service_actions: Optional[list[str]] = None,
    ) -> None:
        _LAST_CALL.clear()
        _LAST_CALL.update(
            from_ac_cycle=from_ac_cycle,
            from_date=from_date,
            cper_data=cper_data,
            designation_serials=designation_serials,
            suppress_service_actions=suppress_service_actions,
            rf_len=len(rf_events),
        )
        return None
