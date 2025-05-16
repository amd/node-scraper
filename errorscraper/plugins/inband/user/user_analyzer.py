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
