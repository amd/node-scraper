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
from typing import Optional, Union
from unittest.mock import MagicMock

import pytest
from framework.common.shared_utils import MockConnectionManager, TestPluginA
from pydantic import BaseModel

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult
from nodescraper.models.datamodel import DataModel
from nodescraper.models.systeminfo import OSFamily, SystemInfo
from nodescraper.pluginregistry import PluginRegistry


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
    regex_match: bool = True


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
            self, data: DummyDataModel, args: Optional[Union[DummyArg, dict]] = None
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


@pytest.fixture
def plugin_registry():
    registry = PluginRegistry()
    registry.plugins = {"TestPluginA": TestPluginA}
    registry.connection_managers = {"MockConnectionManager": MockConnectionManager}
    return registry
