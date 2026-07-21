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
"""Configuration for the long-running Redfish event daemon."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs

from .config import EventStreamConfig, EventTargetConfig
from .trigger_engine import TriggerConfig


class HttpServerConfig(BaseModel):
    """Optional HTTP endpoints for webhook ingest and live recommendations."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = Field(default=8081, ge=1, le=65535)
    webhook_path_prefix: str = "/hook"
    recommendations_path: str = "/recommendations"
    status_path: str = "/status"

    @model_validator(mode="after")
    def _normalize_paths(self) -> HttpServerConfig:
        self.webhook_path_prefix = _normalize_path(self.webhook_path_prefix)
        self.recommendations_path = _normalize_path(self.recommendations_path)
        self.status_path = _normalize_path(self.status_path)
        return self


class DaemonConfig(BaseModel):
    """Full daemon configuration loaded from JSON."""

    stream: EventStreamConfig = Field(default_factory=EventStreamConfig)
    targets: list[EventTargetConfig]
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    analysis: ServiceabilityAnalyzerArgs
    http: HttpServerConfig = Field(default_factory=HttpServerConfig)

    @model_validator(mode="after")
    def _require_targets(self) -> DaemonConfig:
        if not self.targets:
            raise ValueError("At least one target is required")
        return self


def _normalize_path(value: str) -> str:
    text = str(value).strip() or "/"
    if not text.startswith("/"):
        text = f"/{text}"
    return text.rstrip("/") or "/"


def load_daemon_config(path: str | Path) -> DaemonConfig:
    """Load and validate a daemon JSON config file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Daemon config not found: {config_path}")
    raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    return DaemonConfig.model_validate(raw)
