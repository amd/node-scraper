# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from typing import Literal, Optional, Union

from nodescraper.utils import (
    bytes_to_human_readable,
    convert_to_bytes,
    find_annotation_in_container,
    unit_size_to_bytes,
)


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
    assert bytes_to_human_readable(2 << 40) == "2.0 TB"


def test_convert_to_bytes_iec_suffix_is_binary():
    """Gi and Ti are gibibytes and tebibytes, not decimal G and T."""
    assert convert_to_bytes("2016Gi") == 2016 * 1024**3
    assert convert_to_bytes("4Ti") == 4 * 1024**4
    assert convert_to_bytes("2G") == 2 * 10**9
    assert convert_to_bytes("2G", si=False) == 2 * 1024**3


def test_bytes_to_human_readable_petabytes():
    """PB is a documented unit, so petabyte scale values must not be reported in TB."""
    assert bytes_to_human_readable(2 << 50) == "2.0 PB"


def test_unit_size_to_bytes_treats_gb_as_binary():
    """GB and GiB labels both use 1024**3, matching convert_to_bytes."""
    assert unit_size_to_bytes(256, "GB") == 256 * 1024**3
    assert unit_size_to_bytes("256", "GiB") == 256 * 1024**3


def test_unit_size_to_bytes_rejects_unknown_unit():
    """An unrecognized unit is not treated as raw bytes."""
    assert unit_size_to_bytes(256, "FOO") is None
    assert unit_size_to_bytes("n/a", "GB") is None
