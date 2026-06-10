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
from typing import Optional

from pydantic import Field, field_validator, model_validator

from nodescraper.models import CollectorArgs


class CommandSpec(CollectorArgs):
    """One named shell command and optional per-command overrides."""

    name: str = Field(description="Stable name for this command, used by analysis checks.")
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
    include_stdout: Optional[bool] = Field(
        default=None,
        description="Store stdout in the data model. When omitted, uses collection_args.include_stdout.",
    )

    @field_validator("name", "command", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "CommandSpec":
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.command:
            raise ValueError("command must not be empty")
        return self


class GenericCollectionCollectorArgs(CollectorArgs):
    commands: list[CommandSpec] = Field(
        default_factory=list,
        description="Named commands to run. Each entry must include 'name' and 'command'.",
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
    include_stdout: bool = Field(
        default=True,
        description="Default setting for storing stdout in the data model for analysis.",
    )

    @field_validator("commands", mode="before")
    @classmethod
    def _reject_plain_string_commands(cls, value: Optional[list[object]]) -> object:
        if not value:
            return []
        for item in value:
            if isinstance(item, str):
                raise ValueError("Each command must be an object with 'name' and 'command' fields")
        return value

    @model_validator(mode="after")
    def _validate_unique_command_names(self) -> "GenericCollectionCollectorArgs":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for cmd in self.commands:
            if cmd.name in seen:
                duplicates.add(cmd.name)
            seen.add(cmd.name)
        if duplicates:
            raise ValueError(f"Duplicate command name(s): {sorted(duplicates)}")
        return self
