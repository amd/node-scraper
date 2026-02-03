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
from typing import Literal, Optional, Type, get_args, get_origin

from pydantic import BaseModel

from nodescraper.cli.constants import META_VAR_MAP
from nodescraper.cli.inputargtypes import bool_arg, dict_arg
from nodescraper.interfaces.plugin import PluginInterface
from nodescraper.models import DataModel
from nodescraper.typeutils import TypeUtils


class DynamicParserBuilder:
    """Dynamically build an argparse parser based on function type annotations or pydantic model types"""

    def __init__(self, parser: argparse.ArgumentParser, plugin_class: Type[PluginInterface]):
        self.parser = parser
        self.plugin_class = plugin_class

    def build_plugin_parser(self) -> dict:
        """Add parser argument based on arguments in a plugin run function signature"""
        skip_args = ["self", "preserve_connection", "max_event_priority_level"]
        type_map = TypeUtils.get_func_arg_types(self.plugin_class.run, self.plugin_class)

        model_type_map = {}

        for arg, arg_data in type_map.items():
            if arg in skip_args:
                continue

            type_class_map = {
                type_class.type_class: type_class for type_class in arg_data.type_classes
            }

            # skip args where generic type has been set to None
            if type(None) in type_class_map:
                continue

            model_arg = self.get_model_arg(type_class_map)

            # only add cli args for top level model args
            if model_arg:
                model_args = self.build_model_arg_parser(model_arg, arg_data.required)
                for model_arg in model_args:
                    model_type_map[model_arg] = arg
            else:
                self.add_argument(type_class_map, arg.replace("_", "-"), arg_data.required)

        return model_type_map

    @classmethod
    def get_model_arg(cls, type_class_map: dict) -> Optional[Type[BaseModel]]:
        """Get the first type which is a pydantic model from a type class map

        Args:
            type_class_map (dict): mapping of type classes

        Returns:
            Optional[Type[BaseModel]]: pydantic model type
        """
        return next(
            (
                type_class
                for type_class in type_class_map
                if (
                    isinstance(type_class, type)
                    and issubclass(type_class, BaseModel)
                    and not issubclass(type_class, DataModel)
                )
            ),
            None,
        )

    @classmethod
    def get_literal_choices(cls, type_class_map: dict) -> Optional[list]:
        """Get the choices from a Literal type if present

        Args:
            type_class_map (dict): mapping of type classes

        Returns:
            Optional[list]: list of valid choices for the Literal type, or None if not a Literal
        """
        # Check if Literal is in the type_class_map
        literal_type = type_class_map.get(Literal)
        if literal_type and literal_type.inner_type is not None:
            return None
        return None

    def add_argument(
        self,
        type_class_map: dict,
        arg_name: str,
        required: bool,
        annotation: Optional[Type] = None,
    ) -> None:
        """Add an argument to a parser with an appropriate type

        Args:
            type_class_map (dict): type classes for the arg
            arg_name (str): argument name
            required (bool): whether or not the arg is required
            annotation (Optional[Type]): full type annotation for extracting Literal choices
        """
        # Check for Literal types and extract choices
        literal_choices = None
        if Literal in type_class_map and annotation:
            # Extract all arguments from the annotation
            args = get_args(annotation)
            for arg in args:
                if get_origin(arg) is Literal:
                    literal_choices = list(get_args(arg))
                    break

        if list in type_class_map:
            type_class = type_class_map[list]
            self.parser.add_argument(
                f"--{arg_name}",
                nargs="*",
                type=type_class.inner_type if type_class.inner_type else str,
                required=required,
                metavar=META_VAR_MAP.get(type_class.inner_type, "STRING"),
            )
        elif bool in type_class_map:
            self.parser.add_argument(
                f"--{arg_name}",
                type=bool_arg,
                required=required,
                choices=[True, False],
            )
        elif Literal in type_class_map and literal_choices:
            # Add argument with choices for Literal types
            self.parser.add_argument(
                f"--{arg_name}",
                type=str,
                required=required,
                choices=literal_choices,
                metavar=f"{{{','.join(literal_choices)}}}",
            )
        elif float in type_class_map:
            self.parser.add_argument(
                f"--{arg_name}", type=float, required=required, metavar=META_VAR_MAP[float]
            )
        elif int in type_class_map:
            self.parser.add_argument(
                f"--{arg_name}", type=int, required=required, metavar=META_VAR_MAP[int]
            )
        elif str in type_class_map:
            self.parser.add_argument(
                f"--{arg_name}", type=str, required=required, metavar=META_VAR_MAP[str]
            )
        elif dict in type_class_map or self.get_model_arg(type_class_map):
            self.parser.add_argument(
                f"--{arg_name}", type=dict_arg, required=required, metavar=META_VAR_MAP[dict]
            )
        else:
            self.parser.add_argument(
                f"--{arg_name}", type=str, required=required, metavar=META_VAR_MAP[str]
            )

    def build_model_arg_parser(self, model: type[BaseModel], required: bool) -> list[str]:
        """Add args to a parser based on attributes of a pydantic model

        Args:
            model (type[BaseModel]): input model
            required (bool): whether the args from the model are required

        Returns:
            list[str]: list of model attributes that were added as args to the parser
        """
        type_map = TypeUtils.get_model_types(model)

        for attr, attr_data in type_map.items():
            type_class_map = {
                type_class.type_class: type_class for type_class in attr_data.type_classes
            }

            if type(None) in type_class_map and len(attr_data.type_classes) == 1:
                continue

            # Get the full annotation from the model field
            field = model.model_fields.get(attr)
            annotation = field.annotation if field else None

            self.add_argument(type_class_map, attr.replace("_", "-"), required, annotation)

        return list(type_map.keys())
