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
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from pydantic import ValidationError

from nodescraper.cli.helper import find_datamodel_and_result
from nodescraper.enums import ExecutionStatus
from nodescraper.models import PluginResult, TaskResult
from nodescraper.models.datamodel import DataModel
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.resultcollators.tablesummary import TableSummary

# Default regex for log comparison when plugin has no get_error_matches
_DEFAULT_LOG_ERROR_PATTERN = re.compile(
    r"^.*\b(error|fail|critical|crit|warning|warn|alert|emerg)\b.*$",
    re.MULTILINE | re.IGNORECASE,
)


def _default_log_error_matches(content: str) -> set[str]:
    """Extract lines matching default error keywords; used for log plugins without analyzer regexes."""
    return {
        m.group(0).strip()
        for m in _DEFAULT_LOG_ERROR_PATTERN.finditer(content)
        if m.group(0).strip()
    }


def _get_compare_content(data_model: DataModel) -> Optional[str]:
    """Get log content from datamodel for compare-runs (get_compare_content() or None)."""
    get_content = getattr(data_model, "get_compare_content", None)
    if callable(get_content):
        try:
            out = get_content()
            return out if isinstance(out, str) else None
        except Exception:
            return None
    return None


def _get_error_matches_for_analyzer(analyzer_class: type, content: str) -> set[str]:
    """Get error matches from analyzer.get_error_matches if present, else default keyword match."""
    get_matches = getattr(analyzer_class, "get_error_matches", None)
    if callable(get_matches):
        try:
            return get_matches(content)
        except Exception:
            pass
    return _default_log_error_matches(content)


def _compute_extracted_errors_if_applicable(
    data_model: DataModel,
    plugin_name: str,
    analyzer_class: Optional[type],
    logger: logging.Logger,
) -> Optional[list[str]]:
    """If datamodel has get_compare_content, compute extracted errors in memory (not saved to model or disk)."""
    content = _get_compare_content(data_model)
    if content is None:
        return None
    try:
        if analyzer_class is not None:
            matches = _get_error_matches_for_analyzer(analyzer_class, content)
        else:
            matches = _default_log_error_matches(content)
        return sorted(matches)
    except Exception as e:
        logger.warning(
            "Could not compute extracted_errors for %s: %s",
            plugin_name,
            e,
        )
        return None


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
                if not callable(import_model):
                    logger.warning(
                        "Plugin %s datamodel is .log but has no import_model, skipping.",
                        plugin_name,
                    )
                    continue

                # skipping plugins where import_model is not implemented
                _import_func = getattr(import_model, "__func__", import_model)
                _base_import_func = getattr(
                    DataModel.import_model, "__func__", DataModel.import_model
                )
                if _import_func is _base_import_func:
                    logger.debug(
                        "Skipping %s for plugin %s: .log file not loadable (no custom import_model).",
                        dm_path,
                        plugin_name,
                    )
                    continue
                data_model = import_model(dm_path)
            else:
                dm_payload = json.loads(Path(dm_path).read_text(encoding="utf-8"))
                data_model = data_model_cls.model_validate(dm_payload)
            analyzer_class = getattr(plugin, "ANALYZER", None)
            result[plugin_name] = data_model.model_dump(mode="json")
            extracted = _compute_extracted_errors_if_applicable(
                data_model, plugin_name, analyzer_class, logger
            )
            if extracted is not None:
                result[plugin_name]["extracted_errors"] = extracted
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


# Max length for a single value in the full-diff file (avoids dumping huge .log content).
_FULL_DIFF_VALUE_CAP = 8192


def _format_value(val: Any, max_len: Optional[int] = 80) -> str:
    """Format a value for display; optionally truncate long strings (max_len=None for no truncation)."""
    if val is None:
        return "<missing>"
    s = json.dumps(val) if not isinstance(val, str) else repr(val)
    if max_len is not None and len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _format_value_for_diff_file(val: Any) -> str:
    """Format a value for the diff file; cap very long strings (e.g. journal/dmesg logs)."""
    if val is None:
        return "<missing>"
    s = repr(val) if isinstance(val, str) else json.dumps(val)
    if len(s) > _FULL_DIFF_VALUE_CAP:
        s = s[:_FULL_DIFF_VALUE_CAP] + f" ... [truncated, total {len(s)} characters]"
    return s


def _extracted_errors_compare(
    data1: dict[str, Any], data2: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """If datamodels have extracted_errors, return (errors_only_in_run1, errors_only_in_run2)."""
    err1 = set(data1.get("extracted_errors") or [])
    err2 = set(data2.get("extracted_errors") or [])
    return (sorted(err1 - err2), sorted(err2 - err1))


def _build_full_diff_report(
    path1: str,
    path2: str,
    data1: dict[str, dict[str, Any]],
    data2: dict[str, dict[str, Any]],
    all_plugins: list[str],
) -> str:
    """Build a full diff report (no value truncation) for dumping to file."""
    lines = [
        "Compare-runs full diff report",
        f"Run 1: {path1}",
        f"Run 2: {path2}",
        "",
    ]
    for plugin_name in all_plugins:
        lines.append("=" * 80)
        lines.append(f"Plugin: {plugin_name}")
        lines.append("=" * 80)
        if plugin_name not in data1:
            lines.append("  Not present in run 1.")
            lines.append("")
            continue
        if plugin_name not in data2:
            lines.append("  Not present in run 2.")
            lines.append("")
            continue
        d1, d2 = data1[plugin_name], data2[plugin_name]
        has_extracted_errors = "extracted_errors" in d1 or "extracted_errors" in d2
        if has_extracted_errors:
            only_in_1, only_in_2 = _extracted_errors_compare(d1, d2)
            lines.append("  --- Errors only in run 1 ---")
            for e in only_in_1:
                lines.append(f"  {_format_value_for_diff_file(e)}")
            lines.append("")
            lines.append("  --- Errors only in run 2 ---")
            for e in only_in_2:
                lines.append(f"  {_format_value_for_diff_file(e)}")
            lines.append("")
        diffs = _diff_value(d1, d2, "")
        if not diffs:
            if not has_extracted_errors:
                lines.append("  No differences.")
            lines.append("")
            continue
        if has_extracted_errors:
            lines.append(
                "  (Other field differences below; see above for extracted_errors comparison.)"
            )
            lines.append("")
        lines.append(f"  {len(diffs)} difference(s):")
        for p, v1, v2 in diffs:
            lines.append(f"  --- path: {p} ---")
            lines.append(f"  run1:\n{_format_value_for_diff_file(v1)}")
            lines.append(f"  run2:\n{_format_value_for_diff_file(v2)}")
            lines.append("")
        lines.append("")
    return "\n".join(lines)


def run_compare_runs(
    path1: str,
    path2: str,
    plugin_reg: PluginRegistry,
    logger: logging.Logger,
    skip_plugins: Optional[Sequence[str]] = None,
    include_plugins: Optional[Sequence[str]] = None,
    output_path: Optional[str] = None,
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
        skip_plugins: Optional list of plugin names to exclude from comparison.
        include_plugins: Optional list of plugin names to include; if set, only these are compared.
        output_path: Optional path for full diff report; default is <path1>_<path2>_diff.txt.
    """
    p1 = Path(path1)
    p2 = Path(path2)
    if not p1.exists():
        logger.error("Path not found: %s", path1)
        sys.exit(1)
    if not p1.is_dir():
        logger.error("Path is not a directory: %s", path1)
        sys.exit(1)
    if not p2.exists():
        logger.error("Path not found: %s", path2)
        sys.exit(1)
    if not p2.is_dir():
        logger.error("Path is not a directory: %s", path2)
        sys.exit(1)

    logger.info("Loading run 1 from: %s", path1)
    data1 = _load_plugin_data_from_run(path1, plugin_reg, logger)
    logger.info("Loading run 2 from: %s", path2)
    data2 = _load_plugin_data_from_run(path2, plugin_reg, logger)

    all_plugins = sorted(set(data1) | set(data2))
    if include_plugins is not None:
        include_set = set(include_plugins)
        all_plugins = [p for p in all_plugins if p in include_set]
        logger.info("Including only plugins: %s", ", ".join(sorted(include_set)))
    if skip_plugins:
        skip_set = set(skip_plugins)
        all_plugins = [p for p in all_plugins if p not in skip_set]
        if skip_set:
            logger.info("Skipping plugins: %s", ", ".join(sorted(skip_set)))
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

        d1, d2 = data1[plugin_name], data2[plugin_name]
        diffs = _diff_value(d1, d2, "")
        if "extracted_errors" in d1 or "extracted_errors" in d2:
            only_in_1, only_in_2 = _extracted_errors_compare(d1, d2)
            msg_lines = [
                f"Errors only in run 1: {len(only_in_1)}; only in run 2: {len(only_in_2)}.",
            ]
            if only_in_1 or only_in_2:
                if only_in_1:
                    msg_lines.append("  Run 1 only (first 3):")
                    for e in only_in_1[:3]:
                        msg_lines.append(f"    {_format_value(e, max_len=120)}")
                if only_in_2:
                    msg_lines.append("  Run 2 only (first 3):")
                    for e in only_in_2[:3]:
                        msg_lines.append(f"    {_format_value(e, max_len=120)}")
            status = ExecutionStatus.WARNING if (only_in_1 or only_in_2) else ExecutionStatus.OK
            plugin_results.append(
                PluginResult(
                    source=plugin_name,
                    status=status,
                    message="\n".join(msg_lines),
                )
            )
        elif not diffs:
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

    out_file = output_path
    if not out_file:
        out_file = f"{Path(path1).name}_{Path(path2).name}_diff.txt"
    full_report = _build_full_diff_report(path1, path2, data1, data2, all_plugins)
    Path(out_file).write_text(full_report, encoding="utf-8")
    logger.info("Full diff report written to: %s", out_file)

    table_summary = TableSummary(logger=logger)
    table_summary.collate_results(plugin_results=plugin_results, connection_results=[])
    print(f"Diff file written to {out_file}")  # noqa: T201
