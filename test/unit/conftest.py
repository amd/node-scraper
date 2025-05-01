from pathlib import Path
from unittest.mock import MagicMock

import pytest

from errorscraper.models.datamodel import DataModel
from errorscraper.models.systeminfo import OSFamily, SystemInfo


@pytest.fixture
def system_info():
    return SystemInfo(name="test_host", platform="X", os_family=OSFamily.LINUX, sku="GOOD")


@pytest.fixture
def conn_mock():
    return MagicMock()


@pytest.fixture
def plugin_fixtures_path():
    return Path(__file__).parent / "plugin/fixtures"


class DummyDataModel(DataModel):
    foo: int


@pytest.fixture
def dummy_data_model():
    return DummyDataModel


@pytest.fixture
def framework_fixtures_path():
    return Path(__file__).parent / "fixtures"
