import re
from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import DkmsAnalyzerArgs
from .dkmsdata import DkmsDataModel


class DkmsAnalyzer(DataAnalyzer[DkmsDataModel, DkmsAnalyzerArgs]):
    """Check dkms matches expected status and version"""

    DATA_MODEL = DkmsDataModel

    def analyze_data(
        self, data: DkmsDataModel, args: Optional[DkmsAnalyzerArgs] = None
    ) -> TaskResult:
        """ """
        # Check if the required data is provided
        if not args:
            self.result.message = "DKMS analysis args not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        # Convert the status and version to lists if they are not already
        check_map = {
            "status": args.dkms_status,
            "version": args.dkms_version,
        }

        error_state = False

        for check, accepted_values in check_map.items():
            for accepted_value in accepted_values:
                actual_value = getattr(data, check)
                if args.regex_match:
                    try:
                        regex_data = re.compile(accepted_value)
                    except re.error:
                        self._log_event(
                            category=EventCategory.RUNTIME,
                            description=f"DKMS {check} regex is invalid",
                            data={"regex": accepted_value},
                            priority=EventPriority.ERROR,
                        )
                    if regex_data.match(actual_value):
                        break
                elif actual_value == accepted_value:
                    break
            else:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description=f"DKMS {check} has an unexpected value",
                    data={"expected": accepted_values, "actual": actual_value},
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
                error_state = True

        if error_state:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = "DKMS data mismatch"

        return self.result
