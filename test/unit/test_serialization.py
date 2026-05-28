###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
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
from pydantic import BaseModel

from nodescraper.serialization import safe_dump_to_json_dict


class _Sample(BaseModel):
    a: int
    b: str = "x"


def test_safe_dump_to_json_dict_round_trip() -> None:
    m = _Sample(a=7)
    d = safe_dump_to_json_dict(m)
    assert d == {"a": 7, "b": "x"}


def test_safe_dump_to_json_dict_exclude() -> None:
    m = _Sample(a=7)
    d = safe_dump_to_json_dict(m, exclude={"b"})
    assert d == {"a": 7}


def test_safe_dump_falls_back_when_model_dump_json_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Sample(a=3)

    def _boom(self, **kwargs):
        raise RuntimeError("json path failed")

    monkeypatch.setattr(_Sample, "model_dump_json", _boom)
    d = safe_dump_to_json_dict(m)
    assert d == {"a": 3, "b": "x"}


def test_safe_dump_chains_when_both_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Sample(a=1)

    def _boom_json(self, **kwargs):
        raise RuntimeError("first")

    def _boom_dump(self, **kwargs):
        raise RuntimeError("second")

    monkeypatch.setattr(_Sample, "model_dump_json", _boom_json)
    monkeypatch.setattr(_Sample, "model_dump", _boom_dump)
    with pytest.raises(RuntimeError, match="second") as exc_info:
        safe_dump_to_json_dict(m)
    assert exc_info.value.__cause__ is not None
    assert "first" in str(exc_info.value.__cause__)
