import inspect
import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


class TypeUtils:

    @classmethod
    def get_func_arg_types(cls, target, class_type=None) -> dict[str, Any]:
        if class_type and class_type.__orig_bases__ and len(class_type.__orig_bases__) > 0:
            gen_base = class_type.__orig_bases__[0]
            class_org = get_origin(gen_base)
            args = get_args(gen_base)

            gen_map = dict(zip(class_org.__parameters__, args, strict=False))
        else:
            gen_map = {}

        type_map = {}
        skip_args = ["self"]
        for arg, param in inspect.signature(target).parameters.items():
            if arg in skip_args:
                continue
            arg_types = cls.process_type(param.annotation)
            for i, typ in enumerate(arg_types):
                if typ in gen_map:
                    arg_types[i] = gen_map[typ]
            type_map[arg] = arg_types

        return type_map

    @classmethod
    def process_type(cls, input_type: Any) -> list[Any]:
        origin = get_origin(input_type)
        if origin is None:
            return [input_type]
        if origin in [Union, types.UnionType]:
            input_types = [arg for arg in input_type.__args__ if arg != types.NoneType]
            for i, t in enumerate(input_types):
                origin = get_origin(t)
                if origin is not None:
                    input_types[i] = origin
            return input_types
        else:
            return [origin]

    @classmethod
    def get_model_types(cls, model: type[BaseModel]) -> dict[str, Any]:
        type_map = {}
        for name, field in model.model_fields.items():
            field_types = cls.process_type(field.annotation)
            type_map[name] = field_types

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
