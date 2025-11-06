from nodescraper.base import InBandDataCollector
from nodescraper.enums import ExecutionStatus
from nodescraper.models import TaskResult

from .sample_data import SampleDataModel


class SampleCollector(InBandDataCollector[SampleDataModel, None]):

    DATA_MODEL = SampleDataModel

    def collect_data(self, args=None) -> tuple[TaskResult, SampleDataModel | None]:
        sample_data = SampleDataModel(some_str="example123")
        self.result.message = "Collector ran successfully"
        self.result.status = ExecutionStatus.OK

        return self.result, sample_data
