from enum import IntEnum
from functools import total_ordering


@total_ordering
class EventPriority(IntEnum):
    """Enum defining event priority levels"""

    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
