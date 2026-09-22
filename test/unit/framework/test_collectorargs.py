# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from typing import Optional

import pytest

from nodescraper.models.collectorargs import CollectorArgs


class MyCollectorArgs(CollectorArgs):
    opt_arg: Optional[str] = None
    set_arg: Optional[str] = None


def test_collector_args_forbids_extra():
    """Baseline: extra="forbid" from model_config is honored."""
    with pytest.raises(ValueError):
        MyCollectorArgs(not_a_field=1)


def test_collector_args_dumps_none():
    """model_config declares should serialize all args."""
    args = MyCollectorArgs(set_arg="abc")
    assert args.model_dump() == {
        "html_view": False,
        "set_arg": "abc",
        "opt_arg": None,
    }
