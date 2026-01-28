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
from typing import Dict, List, Optional, Tuple, Union

from pydantic import Field, field_validator, model_validator

from nodescraper.models import AnalyzerArgs
from nodescraper.plugins.inband.cmdline.cmdlineconfig import (
    CmdlineConflictError,
    CmdlineOverride,
    ConflictType,
    OverrideConfig,
    ParameterValueConflict,
    RequiredVsBannedConflict,
)
from nodescraper.plugins.inband.cmdline.cmdlinedata import CmdlineDataModel


class CmdlineAnalyzerArgs(AnalyzerArgs):
    required_cmdline: Union[str, List] = Field(default_factory=list)
    banned_cmdline: Union[str, List] = Field(default_factory=list)
    os_overrides: Dict[str, OverrideConfig] = Field(default_factory=dict)
    platform_overrides: Dict[str, OverrideConfig] = Field(default_factory=dict)

    @field_validator("required_cmdline", mode="before")
    @classmethod
    def validate_required_cmdline(cls, required_cmdline: Union[str, List]) -> List:
        """support str or list input for required_cmdline

        Args:
            required_cmdline (Union[str, list]): required command line arguments

        Returns:
            list: list of required command line arguments
        """
        if isinstance(required_cmdline, str):
            required_cmdline = [required_cmdline]

        return required_cmdline

    @field_validator("banned_cmdline", mode="before")
    @classmethod
    def validate_banned_cmdline(cls, banned_cmdline: Union[str, List]) -> List:
        """support str or list input for banned_cmdline

        Args:
            banned_cmdline (Union[str, list]): banned command line arguments

        Returns:
            list: a list of banned command line arguments
        """
        if isinstance(banned_cmdline, str):
            banned_cmdline = [banned_cmdline]

        return banned_cmdline

    @model_validator(mode="after")
    def validate_no_conflicts(self) -> "CmdlineAnalyzerArgs":
        """Validate configuration for conflicts that can be detected at config-time.

        Checks base configuration for conflicts.
        Full validation with OS/platform context happens at runtime in get_effective_config().
        """
        # Check base configuration for conflicts
        base_conflicts = set(self.required_cmdline) & set(self.banned_cmdline)
        if base_conflicts:
            raise CmdlineConflictError(
                ConflictType.REQUIRED_VS_BANNED,
                RequiredVsBannedConflict(
                    conflicting_parameters=list(base_conflicts), source="base configuration"
                ),
            )

        # Check for conflicting parameter values in base configuration
        self._check_parameter_value_conflicts(self.required_cmdline, "base configuration")  # type: ignore[arg-type]

        # Validate each override configuration independently
        # We can't validate cross-override conflicts here because we don't know
        # which overrides will actually be applied (depends on runtime OS/platform)
        for os_name, override in self.os_overrides.items():
            self._validate_override(override, f"os_override: {os_name}")

        for platform_name, override in self.platform_overrides.items():
            self._validate_override(override, f"platform_override: {platform_name}")

        return self

    def _validate_override(self, override: OverrideConfig, source: str) -> None:
        """Validate a single override configuration.

        CONFIG-TIME VALIDATION: Checks for conflicts within a single override.
        Cannot check conflicts between overrides as we don't know which will apply.
        """
        # Check if any parameters are both added to required and banned
        required_adds = set(override.required_cmdline.add)
        banned_adds = set(override.banned_cmdline.add)

        conflicts = required_adds & banned_adds
        if conflicts:
            raise CmdlineConflictError(
                ConflictType.REQUIRED_VS_BANNED,
                RequiredVsBannedConflict(conflicting_parameters=list(conflicts), source=source),
            )

    def _check_parameter_value_conflicts(self, params: List[str], source: str) -> None:
        """Check for conflicting parameter values (e.g., pci=bfsort vs pci=noats)."""
        param_values: Dict[str, str] = {}

        for param in params:
            if "=" in param:
                key, value = param.split("=", 1)
                if key in param_values and param_values[key] != value:
                    raise CmdlineConflictError(
                        ConflictType.PARAMETER_VALUE_CONFLICT,
                        ParameterValueConflict(
                            parameter=key,
                            conflicting_values=[f"{key}={param_values[key]}", f"{key}={value}"],
                            source=source,
                        ),
                    )
                param_values[key] = value

    def _apply_override(self, base_list: List[str], override: CmdlineOverride) -> List[str]:
        """Apply add/remove operations from override configuration."""
        result = base_list.copy()

        # Process removes first
        for item in override.remove:
            if item in result:
                result.remove(item)

        # Then process adds
        for item in override.add:
            if item not in result:
                result.append(item)

        return result

    def get_effective_config(
        self, os_id: Optional[str] = None, platform: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """Get effective cmdline configuration based on OS and platform overrides.

        RUNTIME VALIDATION: Applies overrides and validates final configuration.

        Args:
            os_id: Operating system identifier (e.g., 'ubuntu', 'rhel')
            platform: Platform identifier (e.g., 'mi300x', 'mi250')

        Returns:
            tuple: (effective_required, effective_banned) lists of cmdline arguments

        Raises:
            CmdlineConflictError: If the final configuration has conflicts
        """
        required = list(self.required_cmdline)
        banned = list(self.banned_cmdline)

        # Apply OS overrides if os_id is provided and matches
        if os_id and os_id in self.os_overrides:
            os_override = self.os_overrides[os_id]
            required = self._apply_override(required, os_override.required_cmdline)
            banned = self._apply_override(banned, os_override.banned_cmdline)

        # Apply platform overrides if platform is provided and matches
        if platform and platform in self.platform_overrides:
            platform_override = self.platform_overrides[platform]
            required = self._apply_override(required, platform_override.required_cmdline)
            banned = self._apply_override(banned, platform_override.banned_cmdline)

        # RUNTIME VALIDATION: Check final configuration for conflicts
        conflicts = set(required) & set(banned)
        if conflicts:
            raise CmdlineConflictError(
                ConflictType.REQUIRED_VS_BANNED,
                RequiredVsBannedConflict(
                    conflicting_parameters=list(conflicts),
                    source=f"final configuration for OS '{os_id}' and platform '{platform}'",
                ),
            )

        # Check for parameter value conflicts in final configuration
        self._check_parameter_value_conflicts(
            required, f"final configuration for OS '{os_id}' and platform '{platform}'"
        )

        return required, banned

    @classmethod
    def build_from_model(cls, datamodel: CmdlineDataModel) -> "CmdlineAnalyzerArgs":
        """build analyzer args from data model

        Args:
            datamodel (CmdlineDataModel): data model for plugin

        Returns:
            CmdlineAnalyzerArgs: instance of analyzer args class
        """
        return cls(required_cmdline=datamodel.cmdline)
