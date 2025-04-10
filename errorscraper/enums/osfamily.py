import enum


class OSFamily(enum.Enum):
    """Enum describing operating system of the SUT"""

    WINDOWS = enum.auto()
    UNKNOWN = enum.auto()
    LINUX = enum.auto()
