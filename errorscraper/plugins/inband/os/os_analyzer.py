from typing import Optional

from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult

from .analyzer_args import OsAnalyzerArgs
from .osdata import OsDataModel


class OsAnalyzer(DataAnalyzer[OsDataModel, OsAnalyzerArgs]):
    """Check os matches expected versions"""

    DATA_MODEL = OsDataModel

    def analyze_data(self, data: OsDataModel, args: Optional[OsAnalyzerArgs] = None) -> TaskResult:
        """Analyze the OS name found in the data library

        Parameters
        ----------
        data_library : dict[Type[DataModel], DataModel]
            A dictionary containing the data models. Must contain a key type[OsDataModel] which contains
            the value OsDataModel object
        exp_os : str | list, optional
            Expected OS(s) to test against
            If a string is input it will be transformed into a list see list case for more details.
            If a list is input each element will be tested against the OS name found in the data library
              if the element in `exp_os` is a match to the OS name in the data library the test will pass
              otherwise the test will fail by raising a CRITICAL event
            , by default None
        exact_match : bool, optional
            If true `exp_os` must be equal to `.os_name` in data model.
            If False `exp_os must be a sub-string of `.os_name` in data model
            By default True

        Returns
        -------
        TaskResult
            A TaskResult if no exp_os then ExecutionStatus.NOT_RAN
            If OS name matches exp_os ExecutionStatus.OK
            If OS name does not match exp_os ExecutionStatus.ERRORS_DETECTED due to CRITICAL event
        """
        if not args or not args.exp_os:
            self.result.message = "Expected OS name not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        for os_name in args.exp_os:
            if (os_name == data.os_name and args.exact_match) or (
                os_name in data.os_name and not args.exact_match
            ):
                self.result.message = "OS name matches expected"
                self.result.status = ExecutionStatus.OK
                return self.result

        self.result.message = "OS name mismatch!"
        self.result.status = ExecutionStatus.ERROR
        self._log_event(
            category=EventCategory.OS,
            description=f"{self.result.message}",
            data={"expected": args.exp_os, "actual": data.os_name},
            priority=EventPriority.CRITICAL,
            console_log=True,
        )
        return self.result
