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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import PluginInterface
from nodescraper.models import PluginResult
from nodescraper.plugin_entrypoints import (
    entry_point_distribution_matches,
    entry_point_distribution_name,
    load_plugin_entry_points,
    normalize_distribution_name,
)


def _make_ep(*, name: str, dist_name: str) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    dist = MagicMock()
    dist.metadata = {"Name": dist_name}
    ep.dist = dist
    return ep


def _dup_plugin_cls(marker: str) -> type[PluginInterface]:
    def run(self, **kwargs):
        return PluginResult(source=marker, status=ExecutionStatus.OK)

    return type(
        "DupPlugin",
        (PluginInterface,),
        {
            "CONNECTION_TYPE": object,
            "run": run,
        },
    )


def test_normalize_distribution_name() -> None:
    assert normalize_distribution_name("Foo_Bar") == "foo-bar"
    assert normalize_distribution_name("  Baz  ") == "baz"


def test_entry_point_distribution_name() -> None:
    ep = _make_ep(name="p", dist_name="My_Package")
    assert entry_point_distribution_name(ep) == "my-package"


def test_entry_point_distribution_matches() -> None:
    ep = _make_ep(name="p", dist_name="acme-plugin-pack")
    assert entry_point_distribution_matches(ep, ("acme_plugin_pack",))
    assert not entry_point_distribution_matches(ep, ("other",))


@pytest.fixture
def patch_iter(monkeypatch: pytest.MonkeyPatch) -> list[MagicMock]:
    from nodescraper import plugin_entrypoints as pe

    eps: list[MagicMock] = []

    def _fake_iter(group: str) -> list:
        return eps

    monkeypatch.setattr(pe, "_iter_entry_points", _fake_iter)
    return eps


def test_load_plugin_entry_points_prefers_distribution_last(patch_iter: list[MagicMock]) -> None:
    cls_other = _dup_plugin_cls("other")
    cls_pref = _dup_plugin_cls("prefer")

    ep_pref = _make_ep(name="b", dist_name="prefer-me")
    ep_other = _make_ep(name="a", dist_name="other-dist")
    ep_pref.load = lambda: cls_pref
    ep_other.load = lambda: cls_other

    # prefer-me appears first; loader should reorder so other-dist is applied first, prefer-me wins.
    patch_iter[:] = [ep_pref, ep_other]

    out = load_plugin_entry_points(
        group="nodescraper.plugins",
        prefer_distribution_names=("prefer-me",),
    )
    assert out["DupPlugin"] is cls_pref


def test_load_plugin_entry_points_later_preferred_dist_wins(patch_iter: list[MagicMock]) -> None:
    cls_first = _dup_plugin_cls("first")
    cls_second = _dup_plugin_cls("second")

    ep_a = _make_ep(name="a", dist_name="dist-a")
    ep_b = _make_ep(name="b", dist_name="dist-b")
    ep_a.load = lambda: cls_first
    ep_b.load = lambda: cls_second

    patch_iter[:] = [ep_b, ep_a]

    out = load_plugin_entry_points(
        group="nodescraper.plugins",
        prefer_distribution_names=("dist-a", "dist-b"),
    )
    assert out["DupPlugin"] is cls_second
