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
"""Load and merge distribution entry points for plugins (e.g. ``nodescraper.plugins``).

Embedding applications can install multiple distributions that contribute to the same
entry-point group. Use :func:`load_plugin_entry_points` with *prefer_distribution_names* so
later names in that sequence override earlier ones when two distributions register the same
plugin class name.
"""

from __future__ import annotations

import importlib.metadata
import inspect
from collections.abc import Iterable, Sequence
from typing import Any, Type

from nodescraper.interfaces import PluginInterface


def normalize_distribution_name(name: str) -> str:
    """Normalize a distribution name for comparison (lowercase, ``_`` → ``-``)."""
    return name.strip().lower().replace("_", "-")


def entry_point_distribution_name(ep: importlib.metadata.EntryPoint) -> str | None:
    """Return the normalized distribution name that owns *ep*, or ``None`` if unknown."""
    try:
        dist = ep.dist  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None
    if dist is None:
        return None
    try:
        raw = dist.metadata["Name"]
    except (KeyError, TypeError):
        return None
    return normalize_distribution_name(str(raw))


def entry_point_distribution_matches(
    ep: importlib.metadata.EntryPoint, names: Iterable[str]
) -> bool:
    """True if *ep* belongs to one of the given distribution names (after normalization)."""
    d = entry_point_distribution_name(ep)
    if d is None:
        return False
    allowed = {normalize_distribution_name(n) for n in names}
    return d in allowed


def _iter_entry_points(group: str) -> list[importlib.metadata.EntryPoint]:
    """Resolve *group* for Python 3.9 (dict) and 3.10+ (:meth:`~SelectableGroups.select`)."""
    eps_obj: Any = importlib.metadata.entry_points()
    select = getattr(eps_obj, "select", None)
    if callable(select):
        return list(select(group=group))
    return list(eps_obj.get(group, ()))


def load_plugin_entry_points(
    group: str = "nodescraper.plugins",
    *,
    prefer_distribution_names: Sequence[str] | None = None,
) -> dict[str, Type[PluginInterface]]:
    """Load concrete plugin classes from *group*, optionally giving some distributions priority.

    Entry points are sorted so that distributions **not** listed in
    *prefer_distribution_names* are applied first, then those that are listed, in list order.
    When two entry points yield the same ``plugin_class.__name__``, the later one wins.

    Args:
        group: Entry-point group (default ``nodescraper.plugins``).
        prefer_distribution_names: Distribution names whose plugins should override others
            on name clashes. Later entries in this sequence override earlier ones.

    Returns:
        Map of plugin class name → plugin class.
    """
    eps = _iter_entry_points(group)
    prefer_norm: tuple[str, ...] = tuple()
    if prefer_distribution_names:
        prefer_norm = tuple(normalize_distribution_name(n) for n in prefer_distribution_names)

    def sort_key(ep: importlib.metadata.EntryPoint) -> tuple[int, int, str]:
        d = entry_point_distribution_name(ep)
        if not prefer_norm or d is None:
            return (0, 0, ep.name)
        try:
            idx = prefer_norm.index(d)
        except ValueError:
            return (0, 0, ep.name)
        return (1, idx, ep.name)

    eps.sort(key=sort_key)

    plugins: dict[str, Type[PluginInterface]] = {}
    for ep in eps:
        try:
            plugin_class = ep.load()
        except Exception:
            continue
        if not (
            inspect.isclass(plugin_class)
            and issubclass(plugin_class, PluginInterface)
            and not inspect.isabstract(plugin_class)
        ):
            continue
        if hasattr(plugin_class, "is_valid") and not plugin_class.is_valid():
            continue
        plugins[plugin_class.__name__] = plugin_class

    return plugins


__all__ = [
    "entry_point_distribution_matches",
    "entry_point_distribution_name",
    "load_plugin_entry_points",
    "normalize_distribution_name",
]
