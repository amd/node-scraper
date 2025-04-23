import enum
from functools import total_ordering


@total_ordering
class ExecutionStatus(enum.Enum):
    """Status of module execution"""

    UNSET = 0
    NOT_RAN = 10
    OK = 20
    WARNING = 30
    ERROR = 40
    EXECUTION_FAILURE = 50

    def __lt__(self, other) -> bool:
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
