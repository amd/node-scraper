"""Mock Python service engine for unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from serviceability_dummy_data import (
    DUMMY_ENGINE_VERSION,
    DUMMY_SAG_PID,
    DUMMY_SAG_REVISION,
    DUMMY_SERVICE_ACTION_NUM,
    DUMMY_SERVICE_ACTION_TITLE,
    DUMMY_UNIT_A,
)


class MockServiceEngine:
    def __init__(self, afid_sag: str) -> None:
        self.afid_sag = afid_sag

    def get_service_info(
        self,
        rf_events: list[dict[str, Any]],
        cper_data: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SimpleNamespace:
        del cper_data, kwargs
        service_info: dict[str, dict[str, dict[str, str]]] = {}
        for event in rf_events:
            afid = event.get("Afid")
            unit = event.get("serviceable_unit", DUMMY_UNIT_A)
            if afid is None:
                continue
            service_info.setdefault(str(unit), {})[str(afid)] = {
                "service_action_number": str(DUMMY_SERVICE_ACTION_NUM),
                "title": DUMMY_SERVICE_ACTION_TITLE,
            }
        return SimpleNamespace(
            service_info=service_info,
            afid_sag_metadata={"sag_pid": DUMMY_SAG_PID, "sag_revision": DUMMY_SAG_REVISION},
            engine_version_info={"version": DUMMY_ENGINE_VERSION},
        )
