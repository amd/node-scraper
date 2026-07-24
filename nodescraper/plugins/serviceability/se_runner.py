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
"""Invoke a configured Python or entry-point service hub against collected Redfish events."""
from __future__ import annotations

import importlib
import importlib.metadata
import inspect
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Type, cast

from .afid_sag_paths import validate_afid_sag_path
from .se_adapter import (
    serviceability_block_from_entry_point_hub,
    serviceability_block_from_service_result,
)
from .se_models import AfidEvent, ServiceabilityBlock

HUB_ENTRY_POINT_GROUP = "amd.serviceability_engines"


def _signature_accepts_var_keyword(sig: inspect.Signature) -> bool:
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _instantiate_hub(
    hub_cls: Type[Any],
    config_path: str,
    init_path_kwarg: str,
    hub_options: Optional[dict[str, Any]],
) -> Any:
    """Construct the hub with ``config_path`` under ``init_path_kwarg``, plus matching options."""
    init_sig = inspect.signature(hub_cls.__init__)
    kwargs: dict[str, Any] = {init_path_kwarg: config_path}
    if not hub_options:
        return hub_cls(**kwargs)
    if _signature_accepts_var_keyword(init_sig):
        merged = dict(hub_options)
        merged[init_path_kwarg] = config_path
        return hub_cls(**merged)
    for key, val in hub_options.items():
        if key in init_sig.parameters:
            kwargs[key] = val
    kwargs[init_path_kwarg] = config_path
    return hub_cls(**kwargs)


def _call_hub_analyze(
    analyze: Callable[..., Any],
    rf_events: list[Any],
    cper_data: Optional[dict[str, Any]],
    hub_options: Optional[dict[str, Any]],
) -> Any:
    """Invoke the hub analyze callable with ``cper_data`` and per-parameter ``hub_options``."""
    sig = inspect.signature(analyze)
    params = sig.parameters
    eo = dict(hub_options or {})

    if _signature_accepts_var_keyword(sig):
        if "cper_data" in params:
            eo["cper_data"] = dict(cper_data) if cper_data else None
        return analyze(list(rf_events), **eo)

    kw = {k: v for k, v in eo.items() if k in params}
    if "cper_data" in params:
        kw["cper_data"] = dict(cper_data) if cper_data else None
    return analyze(list(rf_events), **kw)


class HubRunError(RuntimeError):
    """Raised when the service hub fails or returns invalid output."""


def run_service_hub(
    *,
    hub_python_module: str,
    hub_display_name: Optional[str] = None,
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    rf_events: list[Any],
    cper_data: Optional[dict[str, Any]] = None,
    hub_options: Optional[dict[str, Any]] = None,
    hub_analyze_method: str = "get_service_info",
    hub_init_path_kwarg: str = "afid_sag",
) -> ServiceabilityBlock:
    """Run the configured Python service hub and return a :class:`ServiceabilityBlock`.

    The runner imports ``hub_python_module``, picks the unique class that implements
    ``hub_analyze_method``, constructs it with the config file path passed as
    ``hub_init_path_kwarg``, then calls the analyze method with ``rf_events`` and any
    ``hub_options`` keys that match the method signature (plus ``cper_data`` when
    supported). Result mapping is handled by :func:`serviceability_block_from_service_result`.
    """
    sag_path = Path(afid_sag_path)
    if not sag_path.is_file():
        raise HubRunError(f"Hub config file not found: {afid_sag_path}")

    if not rf_events:
        raise HubRunError(
            "Collected Redfish events are required; re-run collection or use skip_hub."
        )

    label = hub_display_name or hub_python_module
    try:
        mod = importlib.import_module(hub_python_module)
    except ImportError as exc:
        raise HubRunError(f"Cannot import {hub_python_module}: {exc}") from exc

    hub_cls = _resolve_hub_class(mod, hub_analyze_method)

    try:
        instance = _instantiate_hub(
            hub_cls,
            afid_sag_path,
            hub_init_path_kwarg,
            hub_options,
        )
        analyze = getattr(instance, hub_analyze_method)
        result = _call_hub_analyze(
            analyze,
            rf_events,
            cper_data,
            hub_options,
        )
    except Exception as exc:
        raise HubRunError(f"{label} {hub_analyze_method}() failed: {exc}") from exc

    if result is None:
        return ServiceabilityBlock(
            afid_events=list(afid_events),
            solution=[],
            solution_reasoning=f"{label}: no service actions after event filtering.",
        )

    return serviceability_block_from_service_result(
        afid_events,
        result,
        hub_label=label,
        rf_event_count=len(rf_events),
    )


def _is_hub_class(obj: Any, analyze_method: str = "get_service_info") -> bool:
    return inspect.isclass(obj) and callable(getattr(obj, analyze_method, None))


def _resolve_hub_class(mod: Any, analyze_method: str = "get_service_info") -> Type[Any]:
    """Find the hub class in ``mod`` that implements ``analyze_method``."""
    package = mod.__name__
    candidates: list[Type[Any]] = []
    seen: set[int] = set()

    def add_candidate(obj: Any) -> None:
        if not _is_hub_class(obj, analyze_method):
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
        raise HubRunError(
            f"No class with {analyze_method}() found in {package}; "
            "check hub_python_module and hub_analyze_method in analysis_args."
        )
    names = ", ".join(cls.__name__ for cls in candidates)
    raise HubRunError(f"Multiple classes with {analyze_method}() in {package}: {names}.")


class EntryPointHubHook(Protocol):
    name: str

    def analyze(self, request: dict[str, Any]) -> dict[str, Any]: ...


def _entry_points_for_group(group: str):
    try:
        return importlib.metadata.entry_points(group=group)  # type: ignore[call-arg]
    except TypeError:
        all_eps = importlib.metadata.entry_points()  # type: ignore[assignment]
        return all_eps.get(group, [])  # type: ignore[attr-defined]


def list_hub_entry_point_names() -> list[str]:
    """Return registered hub entry point names."""
    return sorted({ep.name for ep in _entry_points_for_group(HUB_ENTRY_POINT_GROUP)})


def load_hub_from_entry_point(hub_name: str = "amdse") -> EntryPointHubHook:
    """Load and instantiate a service hub from a registered entry point."""
    wanted = str(hub_name).strip()
    if not wanted:
        raise HubRunError("hub_entry_point must be non-empty")

    matches = [ep for ep in _entry_points_for_group(HUB_ENTRY_POINT_GROUP) if ep.name == wanted]
    if not matches:
        available = ", ".join(list_hub_entry_point_names()) or "(none installed)"
        raise HubRunError(
            f"Service hub {wanted!r} not found among registered hub entry points; "
            f"available: {available}. Install the package that registers this hub entry point."
        )

    try:
        loaded = matches[0].load()
    except Exception as exc:  # noqa: BLE001
        raise HubRunError(f"Failed to load service hub {wanted!r}: {exc}") from exc

    if inspect.isclass(loaded):
        try:
            return cast(EntryPointHubHook, loaded())
        except Exception as exc:  # noqa: BLE001
            raise HubRunError(f"Failed to instantiate service hub {wanted!r}: {exc}") from exc
    return cast(EntryPointHubHook, loaded)


def afid_events_to_entry_point_payload(events: list[AfidEvent]) -> list[dict[str, Any]]:
    """Convert AfidEvent models to the request shape expected by entry-point hub hooks."""
    payload: list[dict[str, Any]] = []
    for event in events:
        payload.append(
            {
                "afid": event.afid,
                "serviceable_unit": event.serviceable_unit,
                "count": 1,
            }
        )
    return payload


def run_entry_point_hub(
    *,
    hub_entry_point: str,
    hub_display_name: Optional[str] = None,
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    rf_event_count: int = 0,
) -> ServiceabilityBlock:
    """Run a registered entry-point service hub and return a :class:`ServiceabilityBlock`."""
    if not afid_events:
        raise HubRunError("No AFID events to analyze")

    validate_afid_sag_path(afid_sag_path)
    label = hub_display_name or hub_entry_point
    hub = load_hub_from_entry_point(hub_entry_point)
    request = {
        "afid_sag_path": afid_sag_path,
        "afid_events": afid_events_to_entry_point_payload(afid_events),
    }
    try:
        hub_result = hub.analyze(request)
    except Exception as exc:  # noqa: BLE001
        hub_label = getattr(hub, "name", label)
        raise HubRunError(f"Service hub {hub_label!r} analyze failed: {exc}") from exc

    if not isinstance(hub_result, dict):
        raise HubRunError(
            f"Service hub {hub_entry_point!r} returned {type(hub_result).__name__}, expected dict"
        )

    return serviceability_block_from_entry_point_hub(
        afid_events,
        hub_result,
        hub_label=label,
        rf_event_count=rf_event_count,
        afid_sag_path=afid_sag_path,
    )
