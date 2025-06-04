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
from unittest.mock import MagicMock

from pydantic import BaseModel

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import ConnectionManager, PluginInterface
from nodescraper.models import PluginResult, TaskResult


class MockConnectionManager(ConnectionManager):
    # Class variable to store the mock connector
    mock_connector = None

    def __init__(
        self,
        system_info=None,
        logger=None,
        parent=None,
        task_result_hooks=None,
        connection_args=None,
    ):
        super().__init__(
            system_info=system_info,
            logger=logger,
            parent=parent,
            task_result_hooks=task_result_hooks,
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


class TestModelArg(BaseModel):
    model_attr: int = 123


class TestPluginA(PluginInterface[MockConnectionManager, None]):

    CONNECTION_TYPE = MockConnectionManager

    def run(
        self,
        test_bool_arg: bool = True,
        test_str_arg: str = "test",
        test_model_arg: Optional[TestModelArg] = None,
    ):
        return PluginResult(
            source="testA",
            status=ExecutionStatus.ERROR,
        )
