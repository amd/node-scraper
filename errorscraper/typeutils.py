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
import inspect
import types
from typing import Any, Callable, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field


class TypeClass(BaseModel):
    type_class: Any
    inner_type: Optional[Any] = None


class TypeData(BaseModel):
    type_classes: list[TypeClass] = Field(default_factory=list)
    required: bool = False
    default: Any = None


class TypeUtils:

    @classmethod
    def get_generic_map(cls, class_type: Type[Any]) -> dict:
        if class_type.__orig_bases__ and len(class_type.__orig_bases__) > 0:
            gen_base = class_type.__orig_bases__[0]
            class_org = get_origin(gen_base)
            args = get_args(gen_base)
            generic_map = dict(zip(class_org.__parameters__, args, strict=False))
        else:
            generic_map = {}

        return generic_map

    @classmethod
    def get_func_arg_types(
        cls, target: Callable, class_type: Optional[Type[Any]] = None
    ) -> dict[str, TypeData]:

        generic_map = {}

        if class_type:
            generic_map = cls.get_generic_map(class_type)

        type_map = {}
        skip_args = ["self"]
        for arg, param in inspect.signature(target).parameters.items():
            if arg in skip_args:
                continue

            type_data = TypeData()

            type_classes = cls.process_type(param.annotation)
            for type_class in type_classes:
                if type_class.type_class in generic_map:
                    type_class.type_class = generic_map[type_class.type_class]

            type_data.type_classes = type_classes
            if param.default is inspect.Parameter.empty:
                type_data.required = True
            else:
                type_data.default = param.default

            type_map[arg] = type_data

        return type_map

    @classmethod
    def process_type(cls, input_type: type[Any]) -> list[TypeClass]:
        origin = get_origin(input_type)
        if origin is None:
            return [TypeClass(type_class=input_type)]
        if origin in [Union, types.UnionType]:
            type_classes = []
            input_types = [arg for arg in input_type.__args__ if arg != types.NoneType]
            for type_item in input_types:
                origin = get_origin(type_item)
                if origin is None:
                    type_classes.append(TypeClass(type_class=type_item))
                else:
                    type_classes.append(
                        TypeClass(
                            type_class=origin,
                            inner_type=next(
                                (arg for arg in get_args(type_item) if arg != types.NoneType), None
                            ),
                        )
                    )

            return type_classes
        else:
            return [
                TypeClass(
                    type_class=origin,
                    inner_type=next(
                        (arg for arg in get_args(input_type) if arg != types.NoneType), None
                    ),
                )
            ]

    @classmethod
    def get_model_types(cls, model: type[BaseModel]) -> dict[str, TypeData]:
        """Get model attribute type details for a pydantic model

        Args:
            model (type[BaseModel]): model to check types

        Returns:
            dict[str, TypeData]: map of type info
        """
        type_map = {}
        for name, field in model.model_fields.items():
            type_map[name] = TypeData(
                type_classes=cls.process_type(field.annotation),
                required=field.is_required(),
                default=field.default,
            )

        return type_map
