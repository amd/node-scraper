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
"""Run the AMD serviceability engine (Python API, CLI, or custom subprocess)."""
from __future__ import annotations

import importlib
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Optional

from .se_adapter import afid_events_to_engine_input, serviceability_block_from_engine
from .se_models import AfidEvent, SeInputPayload, ServiceabilityBlock

EngineBackend = Literal["python", "cli", "subprocess"]


class SeRunError(RuntimeError):
    """Raised when the serviceability engine fails or returns invalid output."""


def resolve_engine_command(
    *,
    engine_executable: Optional[str] = None,
    engine_entry_point: Optional[str] = None,
) -> list[str]:
    """Build the argv prefix for a subprocess or CLI-backed SE invocation."""
    has_exe = bool(engine_executable and str(engine_executable).strip())
    has_entry = bool(engine_entry_point and str(engine_entry_point).strip())
    if has_exe and has_entry:
        raise ValueError("Provide only one of engine_executable or engine_entry_point.")
    if not has_exe and not has_entry:
        raise ValueError("Provide engine_executable or engine_entry_point.")
    if has_exe:
        return [str(engine_executable).strip()]
    return shlex.split(str(engine_entry_point).strip())


def run_se(
    *,
    engine_backend: EngineBackend = "python",
    engine_python_module: str = "serviceability_engine",
    engine_executable: Optional[str] = None,
    engine_entry_point: Optional[str] = None,
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    extra_args: Optional[list[str]] = None,
    timeout_seconds: int = 600,
    work_dir: Optional[str] = None,
) -> ServiceabilityBlock:
    """Run the SE and return a :class:`ServiceabilityBlock`."""
    sag_path = Path(afid_sag_path)
    if not sag_path.is_file():
        raise SeRunError(f"AFID_SAG file not found: {afid_sag_path}")

    if engine_backend == "python":
        return _run_se_python(
            engine_python_module=engine_python_module,
            afid_events=afid_events,
            afid_sag_path=str(sag_path),
        )
    if engine_backend == "cli":
        return _run_se_cli(
            engine_executable=engine_executable,
            engine_entry_point=engine_entry_point,
            afid_events=afid_events,
            afid_sag_path=str(sag_path),
            extra_args=extra_args,
            timeout_seconds=timeout_seconds,
            work_dir=work_dir,
        )
    return _run_se_subprocess(
        engine_executable=engine_executable,
        engine_entry_point=engine_entry_point,
        afid_events=afid_events,
        afid_sag_path=str(sag_path),
        extra_args=extra_args,
        timeout_seconds=timeout_seconds,
        work_dir=work_dir,
    )


def _run_se_python(
    *,
    engine_python_module: str,
    afid_events: list[AfidEvent],
    afid_sag_path: str,
) -> ServiceabilityBlock:
    try:
        se = importlib.import_module(engine_python_module)
        SagDocument = se.SagDocument
        ServiceabilityEngine = se.ServiceabilityEngine
        EventRecord = se.EventRecord
    except (ImportError, AttributeError) as exc:
        raise SeRunError(
            f"Cannot import {engine_python_module} bindings — install serviceability-engine "
            f"and build the Python extension (uv build)."
        ) from exc

    wire_events = afid_events_to_engine_input(afid_events)
    try:
        sag = SagDocument.from_file(afid_sag_path)
        records = [
            EventRecord(
                afid=str(item["afid"]),
                location=str(item["location"]),
                count=int(item["count"]),
            )
            for item in wire_events
        ]
        analysis = ServiceabilityEngine(sag).analyze(records)
        report = analysis.to_dict()
    except Exception as exc:
        raise SeRunError(f"Serviceability engine analyze() failed: {exc}") from exc

    return serviceability_block_from_engine(afid_events, report)


def _run_se_cli(
    *,
    engine_executable: Optional[str],
    engine_entry_point: Optional[str],
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    extra_args: Optional[list[str]],
    timeout_seconds: int,
    work_dir: Optional[str],
) -> ServiceabilityBlock:
    """Invoke an external engine CLI ``analyze --sag … --input …`` and map stdout JSON."""
    command = resolve_engine_command(
        engine_executable=engine_executable,
        engine_entry_point=engine_entry_point,
    )
    wire_events = afid_events_to_engine_input(afid_events)

    with tempfile.TemporaryDirectory(prefix="nodescraper_se_cli_", dir=work_dir) as tmp:
        input_path = Path(tmp) / "events.json"
        input_path.write_text(json.dumps(wire_events, indent=2), encoding="utf-8")
        argv = [
            *command,
            "analyze",
            "--sag",
            afid_sag_path,
            "--input",
            str(input_path),
        ]
        if extra_args:
            argv.extend(extra_args)
        completed = _run_subprocess(argv, timeout_seconds=timeout_seconds)

    try:
        report = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SeRunError(f"Invalid JSON from serviceability engine CLI: {exc}") from exc

    from .se_adapter import recommendations_from_report_dict

    return serviceability_block_from_engine(
        afid_events,
        report,
        recommendations=recommendations_from_report_dict(report),
    )


def _run_se_subprocess(
    *,
    engine_executable: Optional[str],
    engine_entry_point: Optional[str],
    afid_events: list[AfidEvent],
    afid_sag_path: str,
    extra_args: Optional[list[str]],
    timeout_seconds: int,
    work_dir: Optional[str],
) -> ServiceabilityBlock:
    """Custom subprocess protocol: ``--input`` / ``--output`` / ``--afid-sag``."""
    command = resolve_engine_command(
        engine_executable=engine_executable,
        engine_entry_point=engine_entry_point,
    )
    payload = SeInputPayload(afid_events=afid_events)

    with tempfile.TemporaryDirectory(prefix="nodescraper_se_", dir=work_dir) as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "se_input.json"
        output_path = tmp_path / "se_output.json"
        input_path.write_text(
            json.dumps(payload.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        argv = [
            *command,
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--afid-sag",
            str(Path(afid_sag_path).resolve()),
        ]
        if extra_args:
            argv.extend(extra_args)
        _run_subprocess(argv, timeout_seconds=timeout_seconds)

        if not output_path.is_file():
            raise SeRunError(f"Serviceability engine did not write output file: {output_path}")
        try:
            raw = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SeRunError(f"Invalid JSON from serviceability engine: {exc}") from exc

    block = ServiceabilityBlock.model_validate(raw)
    if not block.afid_events:
        block.afid_events = list(afid_events)
    return block


def _run_subprocess(argv: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess:
    exe = Path(argv[0])
    if not exe.is_file() and not _command_on_path(argv[0]):
        raise SeRunError(f"Serviceability engine not found or not executable: {argv[0]!r}")
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SeRunError(f"Serviceability engine timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise SeRunError(f"Failed to start serviceability engine: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise SeRunError(f"Serviceability engine failed: {detail}")
    return completed


def _command_on_path(name: str) -> bool:
    from shutil import which

    return which(name) is not None
