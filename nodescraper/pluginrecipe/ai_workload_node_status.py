###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""Compatibility shim: use :mod:`nodescraper.pluginrecipe.ai_workloads_node_status` instead."""

from __future__ import annotations

from .ai_workloads_node_status import AIWorkloadsNodeStatus

# Legacy name (singular "Workload") — prefer ``AIWorkloadsNodeStatus``.
AiWorkloadNodeStatus = AIWorkloadsNodeStatus

__all__ = ["AIWorkloadsNodeStatus", "AiWorkloadNodeStatus"]
