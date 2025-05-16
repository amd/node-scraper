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
from typing import Optional, Tuple

import pytest

from errorscraper.enums import ExecutionStatus, SystemInteractionLevel
from errorscraper.interfaces.datacollectortask import DataCollector
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models import TaskResult
from errorscraper.models.datamodel import DataModel
from errorscraper.models.systeminfo import SystemInfo


class DummyDataModel(DataModel):
    foo: int


class DummyResult(TaskResult):
    def __init__(self):
        super().__init__(task="DummyCollector", parent=None)

    def finalize(self, logger):
        pass


class DummyCollector(DataCollector[None, DummyDataModel, None]):
    SUPPORTED_SKUS = {"GOOD"}
    SUPPORTED_PLATFORMS = {"X"}
    DATA_MODEL = DummyDataModel

    def __init__(self, system_info: SystemInfo, connection):
        super().__init__(
            system_info=system_info,
            connection=connection,
            logger=logging.getLogger("test"),
            system_interaction_level=SystemInteractionLevel.PASSIVE,
        )

    def _init_result(self):
        return DummyResult()

    def collect_data(self, args=None) -> Tuple[TaskResult, Optional[DummyDataModel]]:
        self.result.status = ExecutionStatus.OK
        return self.result, None


def test_ok(system_info, conn_mock):
    dc = DummyCollector(system_info, conn_mock)

    calls = []
    # fake events
    dc._log_event = lambda *a, **k: calls.append(("log", a, k))
    # fake calls
    dc._run_hooks = lambda result, data=None: calls.append(("hook", result, data))

    result, data = dc.collect_data()

    assert result.status == ExecutionStatus.OK
    assert ("hook", result, None) in calls


def test_exception(system_info, conn_mock):
    class BadCollector(DummyCollector):
        def collect_data(self, args=None):
            raise ValueError("some-err")

    ec = BadCollector(system_info, conn_mock)
    calls = []
    # fake events
    ec._log_event = lambda category, description, data, priority, console_log: calls.append(
        (description, priority)
    )
    # fake calls
    ec._run_hooks = lambda *a, **k: None

    result, data = ec.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert any("some-err" in desc for desc, _ in calls)


def test_bad_sku(system_info, conn_mock):
    class BadCollector(DummyCollector):
        SUPPORTED_SKUS = {"FOO"}

    with pytest.raises(SystemCompatibilityError):
        BadCollector(system_info, conn_mock)


def test_bad_platform(system_info, conn_mock):
    class BadCollector(DummyCollector):
        SUPPORTED_PLATFORMS = {"BAR"}

    with pytest.raises(SystemCompatibilityError):
        BadCollector(system_info, conn_mock)


def test_good_sku_and_platform(conn_mock):
    args = {"name": "h", "sku": "GOOD", "platform": "X", "os_family": 1}
    info = SystemInfo(**args)
    col = DummyCollector(info, conn_mock)
    res, data = col.collect_data()
    assert res.status == ExecutionStatus.OK


def test_missing_data_model():
    with pytest.raises(TypeError, match="No data model set for DummyCollector1"):

        class DummyCollector1(DataCollector):
            SUPPORTED_SKUS = 1
            SUPPORTED_PLATFORMS = "X"

            def _init_result(self):
                return DummyResult()

            def collect_data(self, args=None):
                return self.result, None


def test_bad_data_model_type():
    with pytest.raises(
        TypeError, match="DATA_MODEL must be a subclass of DataModel in DummyCollector2"
    ):

        class DummyCollector2(DataCollector):
            DATA_MODEL = int
            SUPPORTED_SKUS = 1
            SUPPORTED_PLATFORMS = "X"

            def _init_result(self):
                return DummyResult()

            def collect_data(self, args=None):
                return self.result, None
