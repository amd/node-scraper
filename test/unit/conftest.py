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
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.interfaces import DataAnalyzer
from errorscraper.models import TaskResult
from errorscraper.models.datamodel import DataModel
from errorscraper.models.systeminfo import OSFamily, SystemInfo


@pytest.fixture
def system_info():
    return SystemInfo(name="test_host", platform="X", os_family=OSFamily.LINUX, sku="GOOD")


@pytest.fixture
def conn_mock():
    return MagicMock()


class DummyDataModel(DataModel):
    foo: int


class DummyArg(BaseModel):
    value: int


class DummyResult:
    def __init__(self):
        self.status = ExecutionStatus.OK
        self.message = "test"
        self.events: list[dict] = []

    def finalize(self, logger):
        pass


@pytest.fixture
def dummy_data_model():
    return DummyDataModel


@pytest.fixture
def dummy_arg():
    return DummyArg


@pytest.fixture
def dummy_result():
    return DummyResult


@pytest.fixture
def mock_analyzer():
    class MockAnalyzer(DataAnalyzer[DummyDataModel, DummyArg]):
        DATA_MODEL = DummyDataModel
        logger = logging.getLogger("test_data_analyzer")
        events: list[dict] = []

        def analyze_data(
            self, data: DummyDataModel, args: DummyArg | dict | None = None
        ) -> TaskResult:
            self.result.status = ExecutionStatus.OK
            return self.result

    return MockAnalyzer


@pytest.fixture
def plugin_fixtures_path():
    return Path(__file__).parent / "plugin" / "fixtures"


@pytest.fixture
def logger():
    return logging.getLogger("test_logger")


@pytest.fixture
def framework_fixtures_path():
    return Path(__file__).parent / "framework" / "fixtures"
