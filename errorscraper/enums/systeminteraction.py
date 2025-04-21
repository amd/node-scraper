from enum import IntEnum
from functools import total_ordering


@total_ordering
class SystemInteractionLevel(IntEnum):
    """Interaction levels, used to determine what types of actions can be taken when interacting with system"""

    PASSIVE = 0  # read only data collection
    INTERACTIVE = 1  # enable actions that may modify state of the SUT
    DISRUPTIVE = 2  # enable actions that can interfere with driver or other core components

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
