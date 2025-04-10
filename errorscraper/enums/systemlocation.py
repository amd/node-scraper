import enum


class SystemLocation(enum.Enum):
    """Enum defining location of system"""

    LOCAL = enum.auto()
    REMOTE = enum.auto()
