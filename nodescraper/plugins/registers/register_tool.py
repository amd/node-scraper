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
from importlib.metadata import entry_points
from typing import Any, Optional


def dump_tool_value(value: Any) -> Any:
    """Serialize a register-tool model to JSON-ready data.

    Args:
        value: Model, mapping, or None.

    Returns:
        JSON-ready value, or None when value is None.
    """
    if value is None:
        return None
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


def tool_rows(value: Any) -> list[dict[str, Any]]:
    """Serialize register-tool records to a list of mappings.

    Args:
        value: Collection result or a sequence of records.

    Returns:
        JSON-ready record mappings.
    """
    rows = getattr(value, "records", value)
    dumped = []
    for row in rows:
        item = dump_tool_value(row)
        if not isinstance(item, dict):
            raise TypeError("register tool record is not a mapping")
        dumped.append(item)
    return dumped


def discover_register_tool(
    name: Optional[str] = None,
    group: Optional[str] = None,
) -> Any:
    """Load a register tool from an installed entry-point group.

    Args:
        name: Optional entry-point name. Required when more than one tool is installed.
        group: Entry-point group used to discover register tools.

    Returns:
        Instantiated register tool from the selected entry point.
    """
    if not group:
        raise RuntimeError("tool_group is required to discover a register tool")

    discovered = entry_points()
    if hasattr(discovered, "select"):
        entries = list(discovered.select(group=group))
    else:
        entries = list(discovered.get(group, []))

    if name is not None:
        entries = [entry for entry in entries if entry.name == name]

    if not entries:
        detail = f" named {name!r}" if name is not None else ""
        raise RuntimeError(f"No {group} entry point{detail} is installed")

    unique_entries = {(entry.name, entry.value): entry for entry in entries}
    if len(unique_entries) > 1:
        names = sorted({entry.name for entry in unique_entries.values()})
        raise RuntimeError(
            f"Multiple {group} entry points found ({', '.join(names)}); "
            "set tool_name to select one"
        )

    tool = next(iter(unique_entries.values())).load()()
    if not callable(getattr(tool, "collect", None)):
        raise RuntimeError(f"{group} entry point does not provide collect()")
    return tool
