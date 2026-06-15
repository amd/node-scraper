###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
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

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel

__all__ = ["safe_dump_to_json_dict"]


def safe_dump_to_json_dict(
    model: BaseModel,
    *,
    exclude: set[str] | frozenset[str] | None = None,
    by_alias: bool = True,
) -> dict[str, Any]:
    """Best-effort JSON-like ``dict`` from a Pydantic model.

    Args:
        model: Model instance to export.
        exclude: Field names to omit (same shape as Pydantic ``exclude`` for sets).
        by_alias: When ``True``, use field aliases in the output.

    Returns:
        A plain ``dict`` suitable for JSON tools and schema validators.
    """
    ex: set[str] | frozenset[str] | None = exclude
    ex_inc = cast(Any, ex)
    try:
        raw = model.model_dump_json(
            by_alias=by_alias,
            exclude=ex_inc,
            serialize_as_any=True,
        )
        return json.loads(raw)
    except Exception as first_exc:
        try:
            dumped = model.model_dump(
                mode="python",
                by_alias=by_alias,
                exclude=ex_inc,
                serialize_as_any=True,
            )
        except Exception as second_exc:
            raise second_exc from first_exc
        return dumped
