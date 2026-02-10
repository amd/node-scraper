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
import json
import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from nodescraper.cli.helper import find_datamodel_and_result
from nodescraper.enums import ExecutionStatus
from nodescraper.models import PluginResult, TaskResult
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.resultcollators.tablesummary import TableSummary


def _load_plugin_data_from_run(
    base_path: str, plugin_reg: PluginRegistry, logger: logging.Logger
) -> dict[str, dict[str, Any]]:
    """Load plugin name -> datamodel (as dict) for all plugins found in a run log directory.

    Args:
        base_path: Path to run log directory (e.g. scraper_logs_*).
        plugin_reg: Plugin registry to resolve DATA_MODEL per plugin.
        logger: Logger for warnings.

    Returns:
        Dict mapping plugin name to the datamodel as a JSON-serializable dict (model_dump).
    """
    result: dict[str, dict[str, Any]] = {}
    found = find_datamodel_and_result(base_path, plugin_reg)

    for dm_path, res_path in found:
        try:
            res_payload = json.loads(Path(res_path).read_text(encoding="utf-8"))
            task_res = TaskResult(**res_payload)
            plugin_name = task_res.parent
        except (json.JSONDecodeError, TypeError, OSError) as e:
            logger.warning("Skipping %s: failed to load result: %s", res_path, e)
            continue

        if plugin_name is None:
            logger.warning("Result %s has no parent plugin name, skipping.", res_path)
            continue

        plugin = plugin_reg.plugins.get(plugin_name)
        if not plugin:
            logger.warning("Plugin %s not found in registry, skipping.", plugin_name)
            continue

        data_model_cls = getattr(plugin, "DATA_MODEL", None)
        if data_model_cls is None:
            logger.warning("Plugin %s has no DATA_MODEL, skipping.", plugin_name)
            continue

        try:
            if dm_path.lower().endswith(".log"):
                import_model = getattr(data_model_cls, "import_model", None)
                if callable(import_model):
                    data_model = import_model(dm_path)
                else:
                    logger.warning(
                        "Plugin %s datamodel is .log but has no import_model, skipping.",
                        plugin_name,
                    )
                    continue
            else:
                dm_payload = json.loads(Path(dm_path).read_text(encoding="utf-8"))
                data_model = data_model_cls.model_validate(dm_payload)
            result[plugin_name] = data_model.model_dump(mode="json")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping %s for plugin %s: %s", dm_path, plugin_name, e)
            continue
        except ValidationError as e:
            logger.warning(
                "Skipping datamodel for plugin %s (validation error): %s",
                plugin_name,
                e,
            )
            continue

    return result


def _diff_value(val1: Any, val2: Any, path: str) -> list[tuple[str, Optional[Any], Optional[Any]]]:
    """Recursively diff two JSON-like values; return list of (path, value_run1, value_run2)."""
    diffs: list[tuple[str, Optional[Any], Optional[Any]]] = []

    if type(val1) is not type(val2):
        diffs.append((path, val1, val2))
        return diffs

    if isinstance(val1, dict):
        all_keys = set(val1) | set(val2)
        for key in sorted(all_keys):
            sub_path = f"{path}.{key}" if path else key
            if key not in val1:
                diffs.append((sub_path, None, val2[key]))
            elif key not in val2:
                diffs.append((sub_path, val1[key], None))
            else:
                diffs.extend(_diff_value(val1[key], val2[key], sub_path))
        return diffs

    if isinstance(val1, list):
        for i in range(max(len(val1), len(val2))):
            sub_path = f"{path}[{i}]"
            v1 = val1[i] if i < len(val1) else None
            v2 = val2[i] if i < len(val2) else None
            if i >= len(val1):
                diffs.append((sub_path, None, v2))
            elif i >= len(val2):
                diffs.append((sub_path, v1, None))
            else:
                diffs.extend(_diff_value(v1, v2, sub_path))
        return diffs

    if val1 != val2:
        diffs.append((path, val1, val2))
    return diffs


def _format_value(val: Any, max_len: int = 80) -> str:
    """Format a value for display; truncate long strings."""
    if val is None:
        return "<missing>"
    s = json.dumps(val) if not isinstance(val, str) else repr(val)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def run_compare_runs(
    path1: str,
    path2: str,
    plugin_reg: PluginRegistry,
    logger: logging.Logger,
) -> None:
    """Compare datamodels from two run log directories and log results.

    For each plugin present in either run:
    - If plugin is only in one run, logs that it was not found in the other run.
    - If plugin is in both runs, computes diff and logs differences or 'no differences'.

    Args:
        path1: Path to first run log directory.
        path2: Path to second run log directory.
        plugin_reg: Plugin registry.
        logger: Logger for output.
    """
    logger.info("Loading run 1 from: %s", path1)
    data1 = _load_plugin_data_from_run(path1, plugin_reg, logger)
    logger.info("Loading run 2 from: %s", path2)
    data2 = _load_plugin_data_from_run(path2, plugin_reg, logger)

    all_plugins = sorted(set(data1) | set(data2))
    if not all_plugins:
        logger.warning("No plugin data found in either run.")
        return

    plugin_results: list[PluginResult] = []
    for plugin_name in all_plugins:
        if plugin_name not in data1:
            plugin_results.append(
                PluginResult(
                    source=plugin_name,
                    status=ExecutionStatus.NOT_RAN,
                    message=f"Plugin not found in run 1 (path: {path1}).",
                )
            )
            continue
        if plugin_name not in data2:
            plugin_results.append(
                PluginResult(
                    source=plugin_name,
                    status=ExecutionStatus.NOT_RAN,
                    message=f"Plugin not found in run 2 (path: {path2}).",
                )
            )
            continue

        diffs = _diff_value(data1[plugin_name], data2[plugin_name], "")
        if not diffs:
            plugin_results.append(
                PluginResult(
                    source=plugin_name,
                    status=ExecutionStatus.OK,
                    message="No differences.",
                )
            )
        else:
            msg_lines = [f"{len(diffs)} difference(s):"]
            for p, v1, v2 in diffs:
                msg_lines.append(f"  {p}: run1={_format_value(v1)}  run2={_format_value(v2)}")
            plugin_results.append(
                PluginResult(
                    source=plugin_name,
                    status=ExecutionStatus.WARNING,
                    message="\n".join(msg_lines),
                )
            )

    table_summary = TableSummary(logger=logger)
    table_summary.collate_results(plugin_results=plugin_results, connection_results=[])
