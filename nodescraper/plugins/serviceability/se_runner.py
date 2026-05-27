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
"""Invoke a configured Python service engine against collected Redfish events."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any, Optional, Type

from .se_adapter import serviceability_block_from_service_result
from .se_models import AfidEvent, ServiceabilityBlock

_ENGINE_METHOD = "get_service_info"


class SeRunError(RuntimeError):
    """Raised when the service engine fails or returns invalid output."""


def run_service_engine(
    *,
    engine_python_module: str,
    engine_display_name: Optional[str] = None,
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    rf_events: list[Any],
    cper_data: Optional[dict[str, Any]] = None,
) -> ServiceabilityBlock:
    """Run a Python service engine and return a :class:`ServiceabilityBlock`."""
    sag_path = Path(afid_sag_path)
    if not sag_path.is_file():
        raise SeRunError(f"AFID_SAG file not found: {afid_sag_path}")

    if not rf_events:
        raise SeRunError(
            "Collected Redfish events are required; re-run collection or use skip_engine."
        )

    label = engine_display_name or engine_python_module
    try:
        mod = importlib.import_module(engine_python_module)
    except ImportError as exc:
        raise SeRunError(f"Cannot import {engine_python_module}: {exc}") from exc

    engine_cls = _resolve_engine_class(mod)

    try:
        instance = engine_cls(afid_sag=afid_sag_path)
        analyze = getattr(instance, _ENGINE_METHOD)
        result = analyze(
            list(rf_events),
            cper_data=dict(cper_data) if cper_data else None,
        )
    except Exception as exc:
        raise SeRunError(f"{label} {_ENGINE_METHOD}() failed: {exc}") from exc

    if result is None:
        return ServiceabilityBlock(
            afid_events=list(afid_events),
            solution=[],
            solution_reasoning=f"{label}: no service actions after event filtering.",
        )

    return serviceability_block_from_service_result(
        afid_events,
        result,
        engine_label=label,
        rf_event_count=len(rf_events),
    )


def _is_engine_class(obj: Any) -> bool:
    return inspect.isclass(obj) and callable(getattr(obj, _ENGINE_METHOD, None))


def _resolve_engine_class(mod: Any) -> Type[Any]:
    """Find the engine class in ``mod`` that implements ``get_service_info``."""
    package = mod.__name__
    candidates: list[Type[Any]] = []
    seen: set[int] = set()

    def add_candidate(obj: Any) -> None:
        if not _is_engine_class(obj):
            return
        key = id(obj)
        if key in seen:
            return
        seen.add(key)
        candidates.append(obj)

    for name in getattr(mod, "__all__", []) or []:
        add_candidate(getattr(mod, name, None))

    for _, obj in inspect.getmembers(mod, inspect.isclass):
        obj_module = getattr(obj, "__module__", "")
        if obj_module == package or obj_module.startswith(f"{package}."):
            add_candidate(obj)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SeRunError(
            f"No class with {_ENGINE_METHOD}() found in {package}; "
            "check engine_python_module in analysis_args."
        )
    names = ", ".join(cls.__name__ for cls in candidates)
    raise SeRunError(f"Multiple classes with {_ENGINE_METHOD}() in {package}: {names}.")
