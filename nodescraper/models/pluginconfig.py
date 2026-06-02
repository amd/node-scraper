###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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

from typing import Any, Optional

from pydantic import BaseModel, Field


class PluginConfig(BaseModel):
    """Model for preset configuration of plugins and result collators"""

    global_args: dict = Field(default_factory=dict)
    plugins: dict[str, dict] = Field(default_factory=dict)
    result_collators: dict[str, dict] = Field(default_factory=dict)
    name: Optional[str] = None
    desc: Optional[str] = None

    @classmethod
    def coerce(cls, config: PluginConfig | dict[str, Any]) -> PluginConfig:
        """Return a ``PluginConfig`` instance from a model or mapping."""
        if isinstance(config, cls):
            return config
        return cls.model_validate(config)

    @classmethod
    def merge(cls, *configs: PluginConfig | dict[str, Any]) -> PluginConfig:
        """Merge recipe plugin configs.

        Plugin entries from later configs overwrite earlier ones with the same name.
        ``name``, ``desc``, ``global_args``, and ``result_collators`` come from the first
        config.
        """
        normalized = [cls.coerce(config) for config in configs]
        merged_plugins: dict[str, dict[str, Any]] = {}
        for config in normalized:
            merged_plugins.update(config.plugins)
        first = normalized[0] if normalized else cls()
        return cls(
            name=first.name,
            desc=first.desc,
            global_args=first.global_args,
            plugins=merged_plugins,
            result_collators=first.result_collators,
        )
