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
import datetime
import inspect
import io
import os
import re
import tarfile
import traceback
from enum import Enum
from pathlib import Path
from typing import Optional, Type, TypeVar

import pytz

TIMEZONE_MAP = {
    "CT": "America/Chicago",
    "CDT": "America/Chicago",
    "CST": "America/Chicago",
    "ET": "America/Toronto",
    "EDT": "America/Toronto",
    "EST": "America/Toronto",
    "PT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "MT": "America/Edmonton",
    "MST": "America/Edmonton",
    "MDT": "America/Edmonton",
    "UTC": "UTC",
    "GMT": "Europe/London",
    "GMT+8": "Asia/Shanghai",
}


T = TypeVar("T")


class AutoNameStrEnum(Enum):
    """For enums where the value is the same as the name of the attribute"""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Name is the attributes name and the return will be its value"""
        return name


def convert_to_utc(date_in: datetime.datetime, tz: str | int | None):
    """Converts a datetime object to UTC timezone.

    - if date time is aware aka `.tzinfo is not None`
        - If `date_in` is aware then it will be converted to UTC timezone, and the timezone string will be ignored.
        - If `date_in` is naive and `tz` is None then it will be assumed that the time is already in UTC and the timezone is set to
        from None to utc

    - If date time is naive `.tzinfo is None`
        - Then `tz` will be used to convert the timezone to UTC

    Args:
        date_in (datetime.datetime): A datetime object, either aware or naive.
        tz (str | int | None): A timezone string, integer or None.
            - If None then it will be assumed that the time is already in UTC.
            - If integer then `date_in` `tzinfo` will be set to UTC and the time will be adjusted based off the integer in minutes.
            - If string then it will be assumed that the time is in the timezone given by the string and the timezone will be converted to UTC.
                - If string should be in TIMEZONE_MAP or form ±HHMM[SS[.ffffff]] or ±HH:MM[SS[.ffffff]].


    Returns:
        datetime.datetime: A datetime object in UTC timezone.
    """
    if date_in.tzinfo is not None:
        # Aware
        if date_in.tzinfo.tzname == "UTC":
            return date_in
        # convert timezone to UTC ignore tz
        return date_in.astimezone(datetime.timezone.utc)
    if date_in.tzinfo is None and tz is None:
        # naive case and didn't give tz
        return date_in.replace(tzinfo=datetime.timezone.utc)
    if tz is None:
        # Should not get here
        raise ValueError()
    if isinstance(tz, int):
        date_in_aware = date_in.replace(tzinfo=datetime.timezone(datetime.timedelta(minutes=tz)))
        return date_in_aware.astimezone(datetime.timezone.utc)
    # Assume tz is a string
    if tz in TIMEZONE_MAP:
        # get the timezone
        py_tzinfo = pytz.timezone(TIMEZONE_MAP[tz])
        # Conver from naive to aware
        date = py_tzinfo.localize(date_in)
        # give back UTC
        return date.astimezone(pytz.utc)

    time_zone_only_datetime = datetime.datetime.strptime(tz, "%z")
    # replace no info with the timezone, then convert to UTC
    return date_in.replace(tzinfo=time_zone_only_datetime.tzinfo).astimezone(datetime.timezone.utc)


def get_all_subclasses(cls: Type[T]) -> set[Type[T]]:
    """Get an iterable with all subclasses of this class (not including this class)
    Subclasses are presented in no particular order

    Returns:
        An iterable of all subclasses of this class
    """
    subclasses: set[Type[T]] = set()
    for subclass in cls.__subclasses__():
        subclasses = subclasses.union(get_all_subclasses(subclass))
        if not inspect.isabstract(subclass):
            subclasses.add(subclass)
    return subclasses


def get_subclass(
    class_name: str, class_type: Type[T], sub_classes: Optional[list[Type[T]]]
) -> Type[T] | None:
    """get a subclass with a given name

    Args:
        class_name (str): target sub class name
        class_type (Type[T]): class type
        sub_classes (Optional[list[Type[T]]]): list of sub classes to check

    Returns:
        Type[T] | None: sub class or None if no sub class with target name is found
    """
    if not sub_classes:
        sub_classes = list(get_all_subclasses(class_type))

    for sub_class in sub_classes:
        if sub_class.__name__ == class_name:
            return sub_class
    return None


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


def is_subset_dict(small_dict: dict | None, large_dict: dict | None) -> bool:
    """
    Check if one dictionary is a subset of another dictionary.

    This method determines if `small_dict` is a subset of `large_dict`. A dictionary
    is considered a subset if all key-value pairs in `small_dict` are present in
    `large_dict`, and if the value is a dictionary, it recursively checks if the
    nested dictionary is also a subset.

    The dicts must have the keys at the same 'level' to be considered a subset.
    Example:
    `small_dict =               {"key": {"nested_key": "nested_value"}}`
    `large_dict = {"upper_key": {"key": {"nested_key": "nested_value", "another_nested_key": "another_value"}}}`
    will return False

    `small_dict = {"key": {"nested_key": "nested_value"}}`
    `large_dict = {"key": {"nested_key": "nested_value", "another_nested_key": "another_value"}}`
    will return True

    Args:
        small_dict (dict): The dictionary to check if it is a subset.
        large_dict (dict): The dictionary to check against.

    Returns:
        bool: True if `small_dict` is a subset of `large_dict`, False otherwise.
    """
    if not isinstance(small_dict, dict) or not isinstance(large_dict, dict):
        return False
    if small_dict is None or small_dict == {}:
        return True
    if large_dict is None or large_dict == {}:
        return False
    for key, value in small_dict.items():
        if key not in large_dict:
            return False
        large_value = large_dict[key]
        if isinstance(value, dict) and isinstance(large_value, dict):
            if not is_subset_dict(value, large_value):
                return False
        elif value != large_value:
            return False

    return True


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


def hex_to_int(hex_in: str) -> int | None:
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


def apply_bit_mask(in_hex: str, bit_mask_hex: str) -> str | None:
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


def apply_bit_mask_int(in_int: int, bit_mask_int: int) -> int | None:
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


def get_bit_offset(bit_mask: str) -> int | None:
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


def extract_log(
    file_name: str,
    extraction_filter: Optional[set[str]] = None,
) -> dict[str, io.BytesIO]:
    """Extracts all files from a tar file that contain extraction_filer string in their name

    Parameters
    ----------
    file_name : str
        A string to the file name that will be extracted, must be a tar file
    extraction_filter : Optional[set[str]], optional
        If a string in this set is a sub-string of the file then that file will be extracted by this function,
        for example the tar contains two files `Foo.log` and `Foo.txt` and the set contains `{".log"}`
        then Foo.log will be extracted but `Foo.txt` will not be extracted.
        When this argument is None then pull all files out of .tar, by default None

    Returns
    -------
    dict[str, io.BytesIO]
        Key is the filename and value is the file object in bytes

    Raises
    ------
    FileNotFoundError
        This will be raise when the file_name is not a file or is not a tar file
    Exception
        This will be raised when the tar file is not able to be extracted
    """
    return_data = {}
    if not Path(file_name).is_file() and tarfile.is_tarfile(file_name):
        raise FileNotFoundError
    if extraction_filter is None:
        extraction_filter = set()

    with tarfile.open(file_name, "r") as log_tar:
        for member in log_tar:
            # if filter not given then extract all
            if extraction_filter == set() or any(
                filter in member.name for filter in extraction_filter
            ):
                file_obj = log_tar.extractfile(member.name)
                untar_file_name = Path(member.name).name
                if file_obj is None:
                    continue
                bytes_data = io.BytesIO(file_obj.read())
                return_data[untar_file_name] = bytes_data
                # also add the same object to a key in which the set that got it
    return return_data


def group_extracted_files(
    file_data: dict[str, io.BytesIO], extraction_filter: set[str]
) -> dict[str, dict[str, io.BytesIO] | io.BytesIO]:
    """Group the extracted files based on the extraction filter

    Parameters
    ----------
    file_data : dict[str, io.BytesIO]
        A dictionary where the key is the file name and the value is the file object in bytes
    extraction_filter : set[str]
        A set of strings that will be used to group the files

    Returns
    -------
    dict[str, dict[str, io.BytesIO]]
        A dictionary where the key is the filter and the value is a dictionary where the key is the file name and the value is the file object in bytes
    """
    grouped_data = {}
    for filter_str in extraction_filter:
        grouped_data[filter_str] = {}
    for filter_str in extraction_filter:
        for file_name, file_obj in file_data.items():
            if filter_str == file_name:
                grouped_data[filter_str] = file_obj
                continue
            if filter_str in file_name:
                grouped_data[filter_str].update({file_name: file_obj})
    return grouped_data


def translate_io_bytes_to_str(file_data: dict[str, io.BytesIO]) -> dict[str, str]:
    """Translate the file data from bytes to string, to be used alongside extract_log

    Parameters
    ----------
    file_data : dict[str, io.BytesIO]
        A dictionary where the key is the file name and the value is the file object in bytes

    Returns
    -------
    dict[str, str]
        A dictionary where the key is the file name and the value is the file object in string
    """
    log_files_data = {}
    for file_name, file in file_data.items():
        log_files_data[file_name] = file.read().decode("utf-8", errors="backslashreplace")
    return log_files_data


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
    """converts a bytes int to a human readable sting in KB, MB, or GB

    Args:
        input_bytes (int): bytes integer

    Returns:
        str: human readable string
    """
    kb = round(float(input_bytes) / 1000, 2)

    if kb < 1000:
        return f"{kb}KB"

    mb = round(kb / 1000, 2)

    if mb < 1000:
        return f"{mb}MB"

    gb = round(mb / 1000, 2)
    return f"{gb}GB"
