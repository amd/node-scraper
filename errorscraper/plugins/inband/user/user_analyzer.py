from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import UserAnalyzerArgs
from .userdata import UserDataModel


class UserAnalyzer(DataAnalyzer[UserDataModel, UserAnalyzerArgs]):
    """Check that all the logged in users are allowed"""

    DATA_MODEL = UserDataModel

    def analyze_data(self, data: UserDataModel, args: Optional[UserAnalyzerArgs]) -> TaskResult:
        if not args or not args.allowed_users:
            self.result.message = "User analysis args not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        # Check if the users are allowed
        for user in data.active_users:
            if user not in args.allowed_users:
                self.result.message = "Other users logged in!"
                self.result.status = ExecutionStatus.ERROR
                self._log_event(
                    category=EventCategory.OS,
                    description=f"Detected logged in user that is not allowed: {user}",
                    data={
                        "allowed_users": args.allowed_users,
                    },
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
                return self.result

        self.result.message = "All users are allowed"
        self.result.status = ExecutionStatus.OK
        return self.result
