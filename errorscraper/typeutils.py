import types
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints


class TypeUtils:

    @classmethod
    def get_func_arg_types(cls, func: Callable) -> dict:
        type_map = {}
        for arg, type_hint in get_type_hints(func).items():
            type_map[arg] = cls.process_type(type_hint)

        return type_map

    @classmethod
    def process_type(cls, input_type: Any) -> Any:
        if get_origin(input_type) in [Union, types.UnionType]:
            input_types = [arg for arg in input_type.__args__ if arg != types.NoneType]
            if len(input_types) == 1:
                input_types = input_types[0]
            return input_types
        else:
            return input_type

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
