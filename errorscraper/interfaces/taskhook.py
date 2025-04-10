import abc

from errorscraper.models import TaskResult


class TaskHook(abc.ABC):

    @abc.abstractmethod
    def process_result(self, task_result: TaskResult, **kwargs):
        """post process task result

        Args:
            task_result (TaskResult): input task result
        """
