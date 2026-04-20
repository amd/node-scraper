# Copyright (C) 2026 Advanced Micro Devices, Inc. All rights reserved.

from __future__ import annotations

import importlib.metadata
from pathlib import Path

from nodescraper.connection_profile.loader import ConnectionProfileLoader


def load_connection_profile(path: Path, loader_name: str) -> object:
    """Instantiate the named loader entry point and call :meth:`ConnectionProfileLoader.load`.

    Args:
        path: JSON file path.
        loader_name: Entry point name under ``nodescraper.connection_profile_loaders``.

    Returns:
        Loader return value (often :class:`argparse.Namespace` for use as ``host_cli_args``).
    """
    try:
        eps = importlib.metadata.entry_points(  # type: ignore[call-arg]
            group="nodescraper.connection_profile_loaders"
        )
    except TypeError:
        all_eps = importlib.metadata.entry_points()  # type: ignore[assignment]
        eps = all_eps.get("nodescraper.connection_profile_loaders", [])  # type: ignore[assignment, attr-defined, arg-type]

    matches = [ep for ep in eps if ep.name == loader_name]  # type: ignore[attr-defined]
    if not matches:
        available = [ep.name for ep in eps]  # type: ignore[attr-defined]
        raise KeyError(
            f"No nodescraper.connection_profile_loaders entry named {loader_name!r}; "
            f"available: {available}"
        )
    loader_cls = matches[0].load()  # type: ignore[attr-defined]
    if not isinstance(loader_cls, type) or not issubclass(loader_cls, ConnectionProfileLoader):
        raise TypeError(
            f"Entry point {loader_name!r} must resolve to a subclass of ConnectionProfileLoader; "
            f"got {loader_cls!r}"
        )
    loader = loader_cls()
    return loader.load(path)
