import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
def plugin_fixtures_path():
    return Path(__file__).parent / "plugin/fixtures"


@pytest.fixture

def logger():
    return logging.getLogger("test_logger")

def framework_fixtures_path():
    return Path(__file__).parent / "fixtures"

