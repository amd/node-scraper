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

from __future__ import annotations

import argparse
import copy
import logging
import os
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Optional

from nodescraper.cli.helper import dump_results_to_csv, get_system_info, log_system_info
from nodescraper.cli.invocation import run_plugin_queue_with_invocation
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.models.pluginresult import PluginResult
from nodescraper.pluginregistry import PluginRegistry

_TARGET_META_KEYS = frozenset({"name", "sys_name", "sys_location", "sys_sku", "sys_platform"})
_CONFIG_META_KEYS = frozenset({"targets", "max_workers"})

_worker_plugin_registry: Optional[PluginRegistry] = None


def _get_worker_plugin_registry() -> PluginRegistry:
    """Return a process-local :class:`PluginRegistry` reused across node runs."""
    global _worker_plugin_registry
    if _worker_plugin_registry is None:
        _worker_plugin_registry = PluginRegistry()
    return _worker_plugin_registry


def _init_worker_process() -> None:
    """Pre-warm the process-local plugin registry for ProcessPoolExecutor workers."""
    _get_worker_plugin_registry()


def _reset_worker_plugin_registry_cache() -> None:
    """Clear the process-local registry cache (for tests)."""
    global _worker_plugin_registry
    _worker_plugin_registry = None


@dataclass(frozen=True)
class NodeTarget:
    """One node entry from a multi-target connection config."""

    name: str
    sys_location: str
    connection_config: dict[str, dict[str, Any]]
    sys_sku: Optional[str] = None
    sys_platform: Optional[str] = None


@dataclass(frozen=True)
class NodeRunOutcome:
    """Result of one async node run."""

    name: str
    exit_code: int
    log_path: Optional[str]
    summary: Optional[str] = None
    error: Optional[str] = None


_SUCCESS_PLUGIN_STATUSES = frozenset({ExecutionStatus.OK, ExecutionStatus.WARNING})


def _plugin_results_exit_code(results: list[PluginResult]) -> int:
    """Return non-zero when any plugin did not complete successfully."""
    if not results:
        return 1
    return 0 if all(result.status in _SUCCESS_PLUGIN_STATUSES for result in results) else 1


def _summarize_plugin_results(results: list[PluginResult]) -> str:
    """Build a compact status line for orchestrator logging."""
    if not results:
        return "no plugin results"
    return ", ".join(f"{result.source}={result.status.name}" for result in results)


def normalize_sname(name: str) -> str:
    """Normalize a node name for log directory segments."""
    return name.lower().replace("-", "_").replace(".", "_")


def is_multi_target_connection_config(config: Optional[dict[str, Any]]) -> bool:
    """Return True when *config* declares a non-empty ``targets`` list."""
    return bool(config and isinstance(config.get("targets"), list))


def _connection_keys(config: dict[str, Any]) -> list[str]:
    """Return top-level connection manager keys (excluding config metadata)."""
    return [key for key in config if key not in _CONFIG_META_KEYS]


def _extract_target_connection_config(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Pull connection manager sections out of one target entry."""
    connections: dict[str, dict[str, Any]] = {}
    for key, value in target.items():
        if key in _TARGET_META_KEYS:
            continue
        if not isinstance(value, dict):
            raise argparse.ArgumentTypeError(f"target connection entry '{key}' must be an object")
        connections[key] = value
    return connections


def _host_from_connection_section(section: dict[str, Any]) -> Optional[str]:
    """Return host or hostname from one connection manager params dict."""
    for key in ("hostname", "host"):
        value = section.get(key)
        if value:
            return str(value)
    return None


def _infer_target_name(target: dict[str, Any]) -> str:
    """Derive a display name for a target when ``name`` is omitted."""
    for key in ("name", "sys_name"):
        value = target.get(key)
        if value:
            return str(value)

    inband = target.get("InBandConnectionManager")
    if isinstance(inband, dict):
        hostname = _host_from_connection_section(inband)
        if hostname:
            return hostname

    for key, value in target.items():
        if key in _TARGET_META_KEYS or not isinstance(value, dict):
            continue
        host = _host_from_connection_section(value)
        if host:
            return host

    raise argparse.ArgumentTypeError(
        "each target requires 'name' or a host/hostname in its connection config"
    )


def parse_multi_target_connection_config(
    config: dict[str, Any],
    *,
    default_sys_location: str,
    default_sys_sku: Optional[str] = None,
    default_sys_platform: Optional[str] = None,
) -> list[NodeTarget]:
    """Parse and validate a multi-target connection config."""
    if _connection_keys(config):
        raise argparse.ArgumentTypeError(
            "connection config cannot contain both 'targets' and top-level connection managers"
        )

    raw_targets = config.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise argparse.ArgumentTypeError("connection config 'targets' must be a non-empty list")

    seen_names: set[str] = set()
    parsed: list[NodeTarget] = []
    for index, raw_target in enumerate(raw_targets):
        if not isinstance(raw_target, dict):
            raise argparse.ArgumentTypeError(f"targets[{index}] must be an object")

        name = _infer_target_name(raw_target)
        normalized = normalize_sname(name)
        if normalized in seen_names:
            raise argparse.ArgumentTypeError(f"duplicate target name: {name}")
        seen_names.add(normalized)

        connections = _extract_target_connection_config(raw_target)
        if not connections:
            raise argparse.ArgumentTypeError(
                f"target '{name}' must include at least one connection manager section"
            )

        sys_location = str(raw_target.get("sys_location", default_sys_location)).upper()
        parsed.append(
            NodeTarget(
                name=name,
                sys_location=sys_location,
                connection_config=connections,
                sys_sku=raw_target.get("sys_sku", default_sys_sku),
                sys_platform=raw_target.get("sys_platform", default_sys_platform),
            )
        )
    return parsed


def build_run_log_dir(
    base_log_path: str,
    system_name: str,
    timestamp: str,
) -> str:
    """Create ``{base}/scraper_logs_{sname}_{timestamp}/`` using *system_name* for sname."""
    sname = normalize_sname(system_name)
    run_dir = os.path.join(base_log_path, f"scraper_logs_{sname}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _build_target_system_info(
    target: NodeTarget,
    *,
    fallback: SystemInfo,
) -> SystemInfo:
    """Build per-target :class:`SystemInfo` from a target entry and CLI defaults."""
    location = getattr(SystemLocation, target.sys_location, None)
    if location is None:
        raise argparse.ArgumentTypeError(
            f"invalid sys_location for target '{target.name}': {target.sys_location}"
        )
    return SystemInfo(
        name=target.name,
        sku=target.sys_sku if target.sys_sku is not None else fallback.sku,
        platform=target.sys_platform if target.sys_platform is not None else fallback.platform,
        location=location,
        os_family=fallback.os_family,
        gpu_count=fallback.gpu_count,
        cpu_count=fallback.cpu_count,
        metadata=copy.deepcopy(fallback.metadata or {}),
        vendorid_ep=fallback.vendorid_ep,
    )


def _resolve_max_workers(
    config: dict[str, Any],
    target_count: int,
    cli_max_workers: Optional[int],
) -> int:
    """Resolve worker count from CLI flag, config file, or target count."""
    if cli_max_workers is not None:
        if cli_max_workers < 1:
            raise argparse.ArgumentTypeError("--max-node-workers must be at least 1")
        return min(cli_max_workers, target_count)

    config_workers = config.get("max_workers")
    if config_workers is not None:
        if not isinstance(config_workers, int) or config_workers < 1:
            raise argparse.ArgumentTypeError("connection config max_workers must be a positive int")
        return min(config_workers, target_count)

    return target_count


def _node_run_worker(payload: dict[str, Any]) -> NodeRunOutcome:
    """Run one node in a child process (pickle-safe entry point)."""
    from nodescraper.cli.cli import setup_logger

    target_name = payload["target_name"]
    try:
        plugin_reg = _get_worker_plugin_registry()
        system_info = SystemInfo.model_validate(payload["system_info"])
        plugin_config_inst_list = [
            PluginConfig.model_validate(item) for item in payload["plugin_config_inst_list"]
        ]
        log_path = payload["log_path"]
        logger = setup_logger(
            payload["log_level"],
            log_path,
            console=False,
        )
        parsed_args = argparse.Namespace(
            connection_config=payload["connection_config"],
            sys_interaction_level=payload["sys_interaction_level"],
            reference_config=payload["reference_config"],
        )

        results = run_plugin_queue_with_invocation(
            plugin_reg=plugin_reg,
            parsed_args=parsed_args,
            plugin_config_inst_list=plugin_config_inst_list,
            system_info=system_info,
            log_path=log_path,
            logger=logger,
            timestamp=payload["timestamp"],
            sname=payload["sname"],
            host_cli_args=None,
            session_id=payload["session_id"],
            plugin_run_result_hooks=(),
        )

        log_system_info(log_path, system_info, logger)
        dump_results_to_csv(
            results,
            payload["sname"],
            log_path,
            payload["timestamp"],
            logger,
        )

        if payload["reference_config"]:
            if _plugin_results_exit_code(results) != 0:
                logger.warning(
                    "Skipping reference config write for %s because one or more plugins failed",
                    target_name,
                )
            else:
                logger.info(
                    "Reference config generation is not supported per-node in multi-target runs"
                )

        summary = _summarize_plugin_results(results)
        exit_code = _plugin_results_exit_code(results)
        return NodeRunOutcome(
            name=target_name,
            exit_code=exit_code,
            log_path=log_path,
            summary=summary,
        )
    except Exception as exc:
        return NodeRunOutcome(
            name=target_name,
            exit_code=1,
            log_path=payload.get("log_path"),
            error=str(exc),
        )


def run_multi_node_targets(
    *,
    parsed_args: argparse.Namespace,
    plugin_config_inst_list: list[PluginConfig],
    timestamp: str,
    logger: logging.Logger,
    host_cli_args: Optional[argparse.Namespace] = None,
    plugin_run_result_hooks: Optional[Sequence[Callable[[PluginResult], None]]] = None,
    max_workers: Optional[int] = None,
) -> int:
    """Launch async node-scraper runs for each target in the connection config."""
    if host_cli_args is not None:
        raise argparse.ArgumentTypeError(
            "multi-target connection config is not supported with embedded host CLI args"
        )
    if plugin_run_result_hooks:
        logger.warning("plugin_run_result_hooks are not invoked during multi-target runs")

    connection_config = parsed_args.connection_config
    if not is_multi_target_connection_config(connection_config):
        raise argparse.ArgumentTypeError("connection config does not define targets")

    base_system_info = get_system_info(parsed_args)
    targets = parse_multi_target_connection_config(
        connection_config,
        default_sys_location=parsed_args.sys_location,
        default_sys_sku=base_system_info.sku,
        default_sys_platform=base_system_info.platform,
    )

    worker_count = _resolve_max_workers(connection_config, len(targets), max_workers)
    logger.info(
        "Starting multi-target run for %d node(s) with %d worker(s)",
        len(targets),
        worker_count,
    )

    serialized_plugin_configs = [
        config.model_dump(mode="json") for config in plugin_config_inst_list
    ]
    futures = {}
    outcomes: list[NodeRunOutcome] = []

    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=_init_worker_process,
    ) as executor:
        for target in targets:
            system_info = _build_target_system_info(target, fallback=base_system_info)
            sname = normalize_sname(system_info.name)
            if parsed_args.log_path:
                log_path = build_run_log_dir(parsed_args.log_path, system_info.name, timestamp)
            else:
                log_path = None
            logger.info(
                "Queueing target %s -> %s", system_info.name, log_path or "(logging disabled)"
            )

            payload = {
                "target_name": target.name,
                "system_info": system_info.model_dump(mode="json"),
                "plugin_config_inst_list": serialized_plugin_configs,
                "connection_config": target.connection_config,
                "log_path": log_path,
                "log_level": parsed_args.log_level,
                "timestamp": timestamp,
                "sname": sname,
                "session_id": str(uuid.uuid4()),
                "sys_interaction_level": parsed_args.sys_interaction_level,
                "reference_config": bool(parsed_args.reference_config),
            }
            future = executor.submit(_node_run_worker, payload)
            futures[future] = target.name

        for future in as_completed(futures):
            target_name = futures[future]
            outcome = future.result()
            outcomes.append(outcome)
            if outcome.error:
                logger.error("Target %s failed: %s", target_name, outcome.error)
            elif outcome.exit_code != 0:
                logger.error(
                    "Target %s failed (%s) log: %s",
                    target_name,
                    outcome.summary or "plugin error",
                    outcome.log_path,
                )
            else:
                logger.info(
                    "Target %s succeeded (%s) log: %s",
                    target_name,
                    outcome.summary or "ok",
                    outcome.log_path,
                )

    failed = [outcome for outcome in outcomes if outcome.exit_code != 0]
    if failed:
        logger.error(
            "%d of %d target(s) failed: %s",
            len(failed),
            len(outcomes),
            ", ".join(outcome.name for outcome in failed),
        )
        return 1
    return 0


__all__ = [
    "NodeRunOutcome",
    "NodeTarget",
    "build_run_log_dir",
    "is_multi_target_connection_config",
    "normalize_sname",
    "parse_multi_target_connection_config",
    "run_multi_node_targets",
]
