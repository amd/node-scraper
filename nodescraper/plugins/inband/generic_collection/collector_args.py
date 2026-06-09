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
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator

from nodescraper.models import CollectorArgs


class CommandSpec(BaseModel):
    """One shell command and optional per-command overrides."""

    model_config = {"extra": "forbid"}

    command: str = Field(description="Shell command to run on the target system.")
    sudo: Optional[bool] = Field(
        default=None,
        description="Run with sudo. When omitted, uses collection_args.sudo.",
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        description="Command timeout in seconds. When omitted, uses collection_args.timeout.",
    )


class GenericCollectionCollectorArgs(CollectorArgs):
    commands: list[CommandSpec] = Field(
        default_factory=list,
        description=(
            "Commands to run. Each entry may be a plain string or an object with "
            "'command' and optional 'sudo' / 'timeout' overrides."
        ),
    )
    sudo: bool = Field(
        default=False,
        description="Default sudo setting for commands that do not specify sudo.",
    )
    timeout: int = Field(
        default=300,
        ge=1,
        description="Default per-command timeout in seconds.",
    )

    @field_validator("commands", mode="before")
    @classmethod
    def _normalize_commands(
        cls, value: Optional[list[Union[str, dict, CommandSpec]]]
    ) -> list[Union[str, dict, CommandSpec]]:
        if not value:
            return []
        normalized: list[Union[str, dict, CommandSpec]] = []
        for item in value:
            if isinstance(item, str):
                command = item.strip()
                if command:
                    normalized.append({"command": command})
            else:
                normalized.append(item)
        return normalized
