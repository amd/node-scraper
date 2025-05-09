from unittest.mock import MagicMock

from errorscraper.enums import ExecutionStatus
from errorscraper.interfaces import ConnectionManager
from errorscraper.models import TaskResult


class MockConnectionManager(ConnectionManager):
    # Class variable to store the mock connector
    mock_connector = None

    def __init__(
        self, system_info=None, logger=None, parent=None, task_hooks=None, connection_args=None
    ):
        super().__init__(
            system_info=system_info,
            logger=logger,
            parent=parent,
            task_hooks=task_hooks,
            connection_args=connection_args,
        )
        # Use the class variable if available, otherwise create a new MagicMock
        self.connection = (
            MockConnectionManager.mock_connector
            if MockConnectionManager.mock_connector
            else MagicMock()
        )
        self.result = TaskResult(status=ExecutionStatus.OK)

    def connect(self):
        self.result.status = ExecutionStatus.OK
        return self.result

    def disconnect(self):
        pass
