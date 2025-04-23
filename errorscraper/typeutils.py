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


class TypeUtils:

    @classmethod
    def get_func_arg_types(
        cls, target: Callable, class_type: Optional[Type[Any]] = None
    ) -> dict[str, TypeData]:
        if class_type and class_type.__orig_bases__ and len(class_type.__orig_bases__) > 0:
            gen_base = class_type.__orig_bases__[0]
            class_org = get_origin(gen_base)
            args = get_args(gen_base)
            generic_map = dict(zip(class_org.__parameters__, args, strict=False))
        else:
            generic_map = {}

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
                type_classes=cls.process_type(field.annotation), required=field.is_required()
            )

        return type_map

    @classmethod
    def find_annotation_in_container(
        cls, annotation, target_type
    ) -> tuple[Any, list[Any]] | tuple[None, list[Any]]:
        """Recursively search for a target type in an annotation and return the target type and the containers
        supported container types are generic types, Callable, Tuple, Union, Literal, Final, ClassVar
        and Annotated. If the target type is not found then None is returned.

        Examples:
        find_annotation_in_container(Union[int, str], int) -> int, [Union[int, str]]
        find_annotation_in_container(int | dict[str, list[MyClass]], MyClass) -> MyClass, [list,dict,union]
        find_annotation_in_container(Union[int, str], MyClass) -> None, []

        Parameters
        ----------
        annotation : type
            A type annotation to search for the target type in.
        target_type : type
            The target type to search for.

        Returns
        -------
        tuple[Any, list[Any]] | tuple[None, []]
            The target type and the containers if found, otherwise None and an empty list.
        """
        containers: list[Any] = []
        origin = get_origin(annotation)
        args = get_args(annotation)
        if len(args) == 0 and issubclass(annotation, target_type):
            return annotation, containers
        if isinstance(args, tuple):
            for item in args:
                item_args = get_args(item)
                if len(item_args) > 0:
                    result, container = cls.find_annotation_in_container(item, target_type)
                    containers += container
                    if result:
                        containers.append(origin)
                        return result, containers
                if len(get_args(item)) == 0 and issubclass(item, target_type):
                    containers.append(origin)
                    return item, containers
        return None, []
