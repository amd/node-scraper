import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.models.systeminfo import OSFamily, SystemInfo


@pytest.fixture
def system_info():
    return SystemInfo(
        name="test_host",
        platform="platform_id",
        os_family=OSFamily.LINUX,
    )


@pytest.fixture
def conn_mock():
    return MagicMock()


@pytest.fixture
def fixtures_path():
    return Path(__file__).parent / "plugin" / "fixtures"


class DummyDataModel:
    def __init__(self, foo: int):
        self.foo = foo


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
    class MockAnalyzer:
        DATA_MODEL = DummyDataModel

        def __init__(self):
            self.logger = logging.getLogger("test")
            self.events: list[dict] = []

        def _init_result(self):
            return DummyResult()

        def _log_event(self, category, description, data, priority, console_log):
            self.events.append(
                {
                    "category": category,
                    "description": description,
                    "data": data,
                    "priority": priority,
                }
            )

        def _run_hooks(self, result):
            pass

    return MockAnalyzer
