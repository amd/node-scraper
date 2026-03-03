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
import os
import re
import traceback
from enum import Enum
from typing import Any, List, Optional, Set, Type, TypeVar, Union, get_args, get_origin

T = TypeVar("T")


class AutoNameStrEnum(Enum):
    """For enums where the value is the same as the name of the attribute"""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Name is the attributes name and the return will be its value"""
        return name


def get_exception_traceback(exception: Exception) -> dict:
    """get traceback and exception type from an exception

    Args:
        exception (Exception): exception

    Returns:
        dict: exception details dict
    """
    return {
        "exception_type": type(exception).__name__,
        "traceback": traceback.format_tb(exception.__traceback__),
    }


def get_exception_details(exception: Exception) -> dict:
    """get exception as a string and format in dictionary for event

    Args:
        exception (Exception): exception

    Returns:
        dict: exception details dict
    """
    return {
        "details": str(exception)[:1000],
    }


def str_or_none(val: object) -> Optional[str]:
    """Return a stripped string or None.

    None input, or a string that is empty/whitespace after stripping, becomes None.
    Non-string values are converted to string then stripped. Useful for normalizing
    values from JSON, dicts, or user input into Optional[str] for model fields.

    Args:
        val: Any value (e.g. str, int, None).

    Returns:
        Stripped non-empty string, or None.
    """
    if val is None:
        return None
    s = val.strip() if isinstance(val, str) else str(val).strip()
    return s if s else None


def convert_to_bytes(value: str, si=False) -> int:
    """
    Convert human-readable memory sizes (like GB, MB) to bytes.
    Default to use IEC units.
    Factor of powers of 2, not 10. (e.g. 1KB is interpeted as 1KiB=1024 bytes)
    This can be changed with si=True (1KB=1000 bytes)
    """
    value = value.strip().upper()
    unit_names = ["K", "M", "G", "T", "P", "E", "Z", "Y"]
    if si:
        exponent_base = 10
        exponent_power = 3
    else:
        exponent_base = 2
        exponent_power = 10
    # Extract the numeric part and the unit
    pattern = re.compile(r"(\d+\.?\d*)([YZEPTGMK]?)")
    match = pattern.match(value)
    if not match:
        raise ValueError(f"Invalid memory value: {value}")

    # Handle the numeric value and ensure it's a valid number
    try:
        value = float(match.group(1))
    except ValueError as err:
        raise ValueError(f"Invalid numeric value in: {value}") from err

    unit = match.group(2)

    # Convert the value to bytes
    for unit_index, unit_name in enumerate(unit_names):
        if unit == unit_name:
            return int(float(value) * (exponent_base ** ((unit_index + 1) * exponent_power)))
    # If the unit is not found, it is bytes
    return int(value)


def get_unique_filename(directory, filename) -> str:
    """Checks if the file exists in the directory and returns a new filename if it does.
    Parameters
    ----------
    directory : str
        Directory of the file to be saved
    filename : str
        Proposed name of the file to save, unique filename will be generated based on this
        if it already exists, example: "file.txt" -> "file(1).txt" if "file.txt" already exists
    Returns
    -------
    str
        The new unique filename to save
    """
    filepath = os.path.join(directory, filename)
    if not os.path.isfile(filepath):
        return filename
    name, ext = os.path.splitext(filename)
    count = 1
    while True:
        new_name = f"{name}({count}){ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_name
        count += 1


def pascal_to_snake(input_str: str) -> str:
    """Convert PascalCase to snake_case

    Args:
        input_str (str): string to convert

    Returns:
        str: converted string
    """
    if input_str.isupper():
        return input_str.lower()
    return ("_").join(re.split("(?<=.)(?=[A-Z])", input_str)).lower()


def bytes_to_human_readable(input_bytes: int) -> str:
    """Converts a bytes int to a human-readable string in B, KB, MB, GB, TB, or PB (decimal).

    Args:
        input_bytes (int): bytes integer

    Returns:
        str: human-readable string (e.g. "8.25KB", "7.68TB")
    """
    if input_bytes < 0:
        return "0B"
    if input_bytes == 0:
        return "0B"
    units = [(10**12, "TB"), (10**9, "GB"), (10**6, "MB"), (10**3, "KB"), (1, "B")]
    for scale, label in units:
        if input_bytes >= scale:
            return f"{round(float(input_bytes) / scale, 2)}{label}"
    return "0B"


def find_annotation_in_container(
    annotation, target_type
) -> Union[tuple[Any, list[Any]], tuple[None, list[Any]]]:
    """Recursively search for a target type in an annotation and return the target type and the containers
    supported container types are generic types, Callable, Tuple, Union, Literal, Final, ClassVar
    and Annotated. If the target type is not found then None is returned.

    Examples:
       find_annotation_in_container(Union[int, str], int) -> int, [Union[int, str]]
       find_annotation_in_container(Union[int, dict[str, list[MyClass]]], MyClass) -> MyClass, [list,dict,union]
       find_annotation_in_container(Union[int, str], MyClass) -> None, []

    Parameters
    ----------
    annotation : type
        A type annotation to search for the target type in.
    target_type : type
        The target type to search for.

    Returns
    -------
    Union[tuple[Any, list[Any]], tuple[None, []]]
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
                result, container = find_annotation_in_container(item, target_type)
                containers += container
                if result:
                    containers.append(origin)
                    return result, containers
            if len(get_args(item)) == 0 and issubclass(item, target_type):
                containers.append(origin)
                return item, containers
    return None, []


def shell_quote(s: str) -> str:
    """Single quote fix

    Args:
        s (str): path to be converted

    Returns:
        str: path to be returned
    """
    return "'" + s.replace("'", "'\"'\"'") + "'"


def nice_rotated_name(path: str, stem: str, prefix: str = "rotated_") -> str:
    """Map path to a new local filename, generalized for any stem."""
    base = path.rstrip("/").rsplit("/", 1)[-1]
    s = re.escape(stem)

    if base == stem:
        return f"{prefix}{stem}.log"

    m = re.fullmatch(rf"{s}\.(\d+)\.gz", base)
    if m:
        return f"{prefix}{stem}.{m.group(1)}.gz.log"

    m = re.fullmatch(rf"{s}\.(\d+)", base)
    if m:
        return f"{prefix}{stem}.{m.group(1)}.log"

    middle = base[:-3] if base.endswith(".gz") else base
    return f"{prefix}{middle}.log"


def apply_bit_mask(in_hex: str, bit_mask_hex: str) -> Optional[str]:
    """Extracts bit offset from bit mask, applies the bit mask and offset.

    Args:
        in_hex (str): Hexadecimal input
        bit_mask (str): Hexadecimal bit mask

    Returns:
        str: hexadecimal output after applying bit mask and offset
    """
    if not is_hex(hex_in=in_hex) or not is_hex(hex_in=bit_mask_hex):
        return None
    in_dec = hex_to_int(in_hex)
    bit_mask_dec = hex_to_int(bit_mask_hex)
    bit_offset = get_bit_offset(bit_mask_hex)
    if in_dec is None or bit_mask_dec is None or bit_offset is None:
        return None
    out_dec = (in_dec & bit_mask_dec) >> bit_offset
    return hex(out_dec)


def apply_bit_mask_int(in_int: int, bit_mask_int: int) -> Optional[int]:
    """Extracts bit offset from bit mask, applies the bit mask and offset.

    Args:
        in_int (int): integer input
        bit_mask_int (int): integer bit mask

    Returns:
        int: integer output after applying bit mask and offset
    """
    out_int = (in_int & bit_mask_int) >> get_bit_offset_int(bit_mask_int)
    return out_int


def get_bit_offset_int(bit_mask: int) -> int:
    """Extracts the bit offset from bit mask.
    For ex, bit_mask = 0x0010 (hex) -> 0b00010000 (bin)
    Returns bit offset of 4 (bit position of the "1")

    Args:
        bit_mask (int): hex bit mask

    Returns:
        int: bit offset
    """
    bit_pos = 0
    while bit_mask > 0:
        if bit_mask % 2 == 1:
            return bit_pos
        bit_mask = bit_mask >> 1
        bit_pos += 1

    return 0


def get_bit_offset(bit_mask: str) -> Optional[int]:
    """Extracts the bit offset from bit mask.
    For ex, bit_mask = "0010" (hex) -> 0b00010000 (bin)
    Returns bit offset of 4 (bit position of the "1")

    Args:
        bit_mask (str): hex bit mask

    Returns:
        int: bit offset
    """
    bit_mask_int = hex_to_int(bit_mask)
    bit_pos = 0
    if bit_mask_int is None:
        return None
    while bit_mask_int > 0:
        if bit_mask_int % 2 == 1:
            return bit_pos
        bit_mask_int = bit_mask_int >> 1
        bit_pos += 1

    return 0


def get_all_subclasses(cls: Type[T]) -> Set[Type[T]]:
    """Get an iterable with all subclasses of this class (not including this class)
    Subclasses are presented in no particular order

    Returns:
        An iterable of all subclasses of this class
    """
    subclasses: Set[Type[T]] = set()
    for subclass in cls.__subclasses__():
        subclasses = subclasses.union(get_all_subclasses(subclass))
        if not inspect.isabstract(subclass):
            subclasses.add(subclass)
    return subclasses


def get_subclass(
    class_name: str, class_type: Type[T], sub_classes: Optional[List[Type[T]]]
) -> Optional[Type[T]]:
    """get a subclass with a given name

    Args:
        class_name (str): target sub class name
        class_type (Type[T]): class type
        sub_classes (Optional[List[Type[T]]]): list of sub classes to check

    Returns:
        Optional[Type[T]]: sub class or None if no sub class with target name is found
    """
    if not sub_classes:
        sub_classes = list(get_all_subclasses(class_type))

    for sub_class in sub_classes:
        if sub_class.__name__ == class_name:
            return sub_class
    return None


def hex_to_int(hex_in: str) -> Optional[int]:
    """Converts given hex string to int

    Args:
        hex_in: hexadecimal string

    Returns:
        int: hexadecimal converted to int
    """
    try:
        if not is_hex(hex_in):
            return None
        return int(hex_in, 16)
    except TypeError:
        return None


def is_hex(hex_in: str) -> bool:
    """Returns True or False based on whether the input hexadecimal is indeed hexadecimal

    Args:
        hex_in: hexadecimal string

    Returns:
        bool: True/False whether the input hexadecimal is indeed hexadecimal
    """
    if not hex_in:
        return False

    hex_pattern = re.compile(r"^(0x)?[0-9a-fA-F]+$")
    return bool(hex_pattern.fullmatch(hex_in))


def strip_ansi_codes(text: str) -> str:
    """
    Remove ANSI escape codes from text.

    Args:
        text (str): The text string containing ANSI escape codes.

    Returns:
        str: The text with ANSI escape codes removed.
    """
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)
