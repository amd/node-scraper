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
import argparse
import json
import types
from typing import Generic, Type

from pydantic import ValidationError

from nodescraper.generictypes import TModelType


def log_path_arg(log_path: str) -> str | None:
    """Type function for a log path arg, allows 'none' to be specified to disable logging

    Args:
        log_path (str): log path string

    Returns:
        str | None: log path or None
    """
    if log_path.lower() == "none":
        return None
    return log_path


def bool_arg(str_input: str) -> bool:
    """Converts a string arg input into a bool

    Args:
        str_input (str): string input

    Returns:
        bool: bool value for string
    """
    if str_input.lower() == "true":
        return True
    elif str_input.lower() == "false":
        return False
    raise argparse.ArgumentTypeError("Invalid input, boolean value (True or False) expected")


def dict_arg(str_input: str) -> dict:
    """converts a json string into a dict

    Args:
        str_input (str): input string

    Raises:
        argparse.ArgumentTypeError: if error was seen when loading string into json dict

    Returns:
        dict: dict representation of the json string
    """
    try:
        return json.loads(str_input)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError("Invalid json input for arg") from e


class ModelArgHandler(Generic[TModelType]):
    """Class to handle loading json files into pydantic models"""

    def __init__(self, model: Type[TModelType]) -> types.NoneType:
        self.model = model

    def process_file_arg(self, file_path: str) -> TModelType:
        """load a json file into a pydantic model

        Args:
            file_path (str): json file path

        Raises:
            argparse.ArgumentTypeError: If validation errors were seen when building model

        Returns:
            TModelType: model instance
        """
        data = json_arg(file_path)
        try:
            return self.model(**data)
        except ValidationError as e:
            raise argparse.ArgumentTypeError(
                f"Validation errors when processing {file_path}: {e.errors(include_url=False)}"
            ) from e


def json_arg(json_path: str) -> dict:
    """loads a json file into a dict

    Args:
        json_path (str): path to json file

    Raises:
        argparse.ArgumentTypeError: If file does not exist or could not be decoded

    Returns:
        dict: output dict
    """
    try:
        with open(json_path, "r", encoding="utf-8") as input_file:
            data = json.load(input_file)
        return data
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"File {json_path} contains invalid JSON") from e
    except FileNotFoundError as e:
        raise argparse.ArgumentTypeError(f"Unable to find file: {json_path}") from e
