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
from typing import Any

from pydantic import BaseModel, model_validator


class AnalyzerArgs(BaseModel):
    """Base class for all analyzer arguments.

    This class provides automatic string stripping for all string values
    in analyzer args. All analyzer args classes should inherit from this
    directly.

    """

    model_config = {"extra": "forbid", "exclude_none": True}

    @model_validator(mode="before")
    @classmethod
    def strip_string_values(cls, data: Any) -> Any:
        """Strip whitespace from all string values in analyzer args.

        This validator recursively processes:
        - String values: strips whitespace
        - Lists: strips strings in lists
        - Dicts: strips string values in dicts
        - Other types: left unchanged

        Args:
            data: The input data to validate

        Returns:
            The data with all string values stripped
        """
        if isinstance(data, dict):
            return {k: cls._strip_value(v) for k, v in data.items()}
        return data

    @classmethod
    def _strip_value(cls, value: Any) -> Any:
        """Recursively strip string values.

        Args:
            value: The value to process

        Returns:
            The processed value
        """
        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, list):
            return [cls._strip_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: cls._strip_value(v) for k, v in value.items()}
        return value

    @classmethod
    def build_from_model(cls, datamodel):
        """Build analyzer args instance from data model object

        Args:
            datamodel (TDataModel): data model to use for creating analyzer args

        Raises:
            NotImplementedError: Not implemented error
        """
        raise NotImplementedError(
            "Setting analyzer args from datamodel is not implemented for class: %s", cls.__name__
        )
