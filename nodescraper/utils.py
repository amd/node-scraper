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
import os
import re
import traceback
from enum import Enum
from typing import TypeVar

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


# ROCm Plugin Command Constants
CMD_VERSION_PATHS = [
    "/opt/rocm/.info/version-rocm",
    "/opt/rocm/.info/version",
]
CMD_ROCMINFO = "{rocm_path}/bin/rocminfo"
CMD_ROCM_LATEST = "ls -v -d /opt/rocm-[3-7]* | tail -1"
CMD_ROCM_DIRS = "ls -v -d /opt/rocm*"
CMD_LD_CONF = "grep -i -E 'rocm' /etc/ld.so.conf.d/*"
CMD_ROCM_LIBS = "ldconfig -p | grep -i -E 'rocm'"
CMD_ENV_VARS = "env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'"
CMD_CLINFO = "{rocm_path}/opencl/bin/*/clinfo"
CMD_KFD_PROC = "ls /sys/class/kfd/kfd/proc/"
