#!/usr/bin/env python3
"""Smoke test service hub entry-point integration with an installed hub package."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from nodescraper.plugins.serviceability import AfidEvent, run_entry_point_hub
from nodescraper.plugins.serviceability.se_runner import list_hub_entry_point_names

ROOT = Path(__file__).resolve().parents[1]
COMPAT_SAG = ROOT / "test/unit/plugin/fixtures/afid_sag_se_compat.json"


def resolve_sag_path() -> Path:
    if COMPAT_SAG.is_file():
        return COMPAT_SAG
    home_sag = Path.home() / "AFID_SAG.json"
    if home_sag.is_file():
        maker = ROOT / "tools/make_se_compat_sag.py"
        subprocess.run(
            [sys.executable, str(maker), "--source", str(home_sag), "--output", str(COMPAT_SAG)],
            check=True,
        )
        return COMPAT_SAG
    fixture = ROOT / "test/unit/plugin/fixtures/afid_sag_sample.json"
    if fixture.is_file():
        return fixture
    raise FileNotFoundError("No AFID SAG file found")


def main() -> int:
    print("hub entry points:", list_hub_entry_point_names())  # noqa: T201
    sag = resolve_sag_path()
    print("using sag:", sag)  # noqa: T201
    events = [
        AfidEvent(afid=9001, serviceable_unit="dummy_unit_a", time="2000-01-01T12:00:00+00:00"),
        AfidEvent(afid=9002, serviceable_unit="dummy_unit_b", time="2000-01-01T12:00:00+00:00"),
    ]
    block = run_entry_point_hub(
        hub_entry_point="hub",
        afid_events=events,
        afid_sag_path=str(sag),
        rf_event_count=2,
    )
    print("solutions:", len(block.solution))  # noqa: T201
    print("hub_version:", block.hub_version)  # noqa: T201
    for solution in block.solution[:5]:
        print(  # noqa: T201
            f"  AFID {solution.afid} SA {solution.service_action_num} "
            f"units={solution.serviceable_unit}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
