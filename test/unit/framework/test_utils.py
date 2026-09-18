# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from typing import Literal, Optional, Union

from nodescraper.utils import bytes_to_human_readable, find_annotation_in_container


class Target:
    pass


def test_find_annotation_in_container_union():
    """Baseline: the target type is found inside a Union."""
    assert find_annotation_in_container(Union[int, str], int) == (int, [Union])


def test_find_annotation_in_container_not_found():
    """Baseline: a missing target type returns None."""
    assert find_annotation_in_container(Union[int, str], Target) == (None, [])


def test_find_annotation_in_container_supports_literal():
    """Literal is documented as a supported container and must not raise."""
    assert find_annotation_in_container(Optional[Literal["a", "b"]], Target) == (None, [])


def test_find_annotation_in_container_literal_nested_in_generic():
    """A Literal nested inside another container must not raise."""
    assert find_annotation_in_container(dict[str, Literal["a", "b"]], Target) == (None, [])


def test_bytes_to_human_readable_terabytes():
    """Baseline: a terabyte scale value is rendered with the TB unit."""
    assert bytes_to_human_readable(2 * 10**12) == "2.0TB"


def test_bytes_to_human_readable_petabytes():
    """PB is a documented unit, so petabyte scale values must not be reported in TB."""
    assert bytes_to_human_readable(2 * 10**15) == "2.0PB"
