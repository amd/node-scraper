from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .sample_data import SampleDataModel


class SampleAnalyzer(DataAnalyzer[SampleDataModel, None]):

    DATA_MODEL = SampleDataModel

    def analyze_data(self, data: SampleDataModel, args=None) -> TaskResult:
        if data.some_str != "expected_str":
            self.result.message = "String does not match expected"
            self.result.status = ExecutionStatus.ERROR
            return self.result

            self._log_event(
                category=EventCategory.OS,
                description=f"{self.result.message}",
                data={"expected": "expected_str", "actual": data.some_str},
                priority=EventPriority.CRITICAL,
                console_log=True,
            )
        return self.result
