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
"""Cmdline configuration models and validation classes."""

from enum import Enum
from typing import Any, List, Union

from pydantic import BaseModel, field_validator


class ConflictType(Enum):
    """Types of configuration conflicts that can occur."""

    REQUIRED_VS_BANNED = "required_vs_banned"
    PARAMETER_VALUE_CONFLICT = "parameter_value_conflict"


class RequiredVsBannedConflict(BaseModel):
    """Details for a required vs banned conflict."""

    conflicting_parameters: List[str]
    source: str  # e.g., "base configuration", "os_override: ubuntu", etc.


class ParameterValueConflict(BaseModel):
    """Details for a parameter value conflict."""

    parameter: str  # e.g., "pci"
    conflicting_values: List[str]  # e.g., ["pci=bfsort", "pci=noats"]
    source: str  # e.g., "final configuration for OS 'centos' and platform 'grand-teton'"


class CmdlineConflictError(Exception):
    """Exception raised when cmdline configuration has conflicts."""

    def __init__(
        self,
        conflict_type: ConflictType,
        details: Union[RequiredVsBannedConflict, ParameterValueConflict],
    ):
        """Initialize the conflict error.

        Args:
            conflict_type: Type of conflict from ConflictType enum
            details: Structured conflict details (type depends on conflict_type)
        """
        self.conflict_type = conflict_type
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format a human-readable error message based on conflict type."""
        if self.conflict_type == ConflictType.REQUIRED_VS_BANNED:
            assert isinstance(self.details, RequiredVsBannedConflict)
            return f"Parameters cannot be both required and banned in {self.details.source}: {self.details.conflicting_parameters}"
        elif self.conflict_type == ConflictType.PARAMETER_VALUE_CONFLICT:
            assert isinstance(self.details, ParameterValueConflict)
            return f"Conflicting values for parameter '{self.details.parameter}' in {self.details.source}: {' vs '.join(self.details.conflicting_values)}"
        else:
            return f"Configuration conflict: {self.conflict_type.value}"


class CmdlineOverride(BaseModel):
    """Model for cmdline override configuration.

    This model represents the add/remove operations for cmdline parameters.
    Validation happens at config-time to ensure proper structure.
    """

    add: List[str] = []
    remove: List[str] = []

    @field_validator("add", "remove", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> List[str]:
        """Ensure add/remove are always lists.

        CONFIG-TIME VALIDATION: Converts various input formats to lists.
        This prevents runtime errors from malformed configuration.
        """
        if isinstance(v, str):
            return [v]
        elif isinstance(v, dict) and not v:  # Empty dict
            return []
        elif v is None:
            return []
        return v


class OverrideConfig(BaseModel):
    """Model for OS/platform override configuration.

    Contains overrides for both required and banned cmdline parameters.
    """

    required_cmdline: CmdlineOverride = CmdlineOverride()
    banned_cmdline: CmdlineOverride = CmdlineOverride()
