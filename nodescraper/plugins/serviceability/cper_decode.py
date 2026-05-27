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
"""Decode collected CPER attachments via a configured Python decode module."""
from __future__ import annotations

import base64
import binascii
import importlib
import io
import logging
from typing import Any, Callable, Optional


class CperDecodeError(RuntimeError):
    """Raised when the configured CPER decode module cannot be loaded or decoding fails."""


def _load_decode_callable(
    cper_decode_module: str,
    cper_decode_method: str,
) -> Callable[[io.BytesIO], tuple[int, Any]]:
    """Import a decode callable from analysis_args (module + method name)."""
    try:
        module = importlib.import_module(cper_decode_module)
    except ImportError as exc:
        raise CperDecodeError(
            f"Cannot import cper_decode_module {cper_decode_module!r}: {exc}"
        ) from exc

    decode_fn = getattr(module, cper_decode_method, None)
    if decode_fn is None:
        raise CperDecodeError(
            f"Module {cper_decode_module!r} has no callable {cper_decode_method!r}"
        )
    if not callable(decode_fn):
        raise CperDecodeError(f"{cper_decode_module!r}.{cper_decode_method!r} is not callable")
    return decode_fn


def count_ras_err_entries(decode_payload: Any) -> int:
    """Count RasErr* keys in a decoded CPER triage_result dict."""
    if not isinstance(decode_payload, dict):
        return 0
    triage_result = decode_payload.get("triage_result", {})
    if not isinstance(triage_result, dict):
        return 0
    return sum(1 for key in triage_result if str(key).startswith("RasErr"))


def decode_cper_raw_attachments(
    cper_raw: dict[str, str],
    *,
    cper_decode_module: str,
    cper_decode_method: str = "analyze_cper",
    logger: Optional[logging.Logger] = None,
) -> dict[str, Any]:
    """Decode base64 CPER blobs keyed by Redfish event Id.

    The decode callable must accept a binary file-like object and return
    ``(return_code, decode_dict)``. Results are passed to the service engine as
    ``cper_data``; the engine does not perform CPER decoding itself.

    Returns ``{event_id: {"return_code": int, "decode": dict}}``.
    """
    if not cper_raw:
        return {}

    decode_fn = _load_decode_callable(cper_decode_module, cper_decode_method)

    decoded: dict[str, Any] = {}
    errors: list[str] = []

    for event_id, payload_b64 in cper_raw.items():
        try:
            raw = base64.b64decode(payload_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            errors.append(f"event {event_id}: invalid base64 ({exc})")
            continue

        try:
            return_code, decode_payload = decode_fn(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            msg = f"event {event_id}: {exc}"
            errors.append(msg)
            if logger is not None:
                logger.warning("CPER decode failed for Redfish event %s: %s", event_id, exc)
            continue

        if return_code != 0:
            errors.append(f"event {event_id}: decode return code {return_code}")

        decoded[str(event_id)] = {
            "return_code": return_code,
            "decode": decode_payload,
        }
        if logger is not None:
            ras_count = count_ras_err_entries(decode_payload)
            if return_code == 0:
                logger.info(
                    "CPER decoded for Redfish event %s (return_code=0, %d RasErr entr%s)",
                    event_id,
                    ras_count,
                    "y" if ras_count == 1 else "ies",
                )
            else:
                logger.warning(
                    "CPER decoded for Redfish event %s with non-zero return_code=%s "
                    "(%d RasErr entr%s)",
                    event_id,
                    return_code,
                    ras_count,
                    "y" if ras_count == 1 else "ies",
                )

    if errors and not decoded:
        raise CperDecodeError("; ".join(errors))

    if logger is not None and errors:
        for msg in errors:
            logger.warning("CPER decode issue: %s", msg)

    return decoded
