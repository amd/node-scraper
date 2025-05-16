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
import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.user.analyzer_args import UserAnalyzerArgs
from errorscraper.plugins.inband.user.user_analyzer import UserAnalyzer
from errorscraper.plugins.inband.user.userdata import UserDataModel


@pytest.fixture
def model_obj():
    return UserDataModel(active_users=["user1", "root"])


@pytest.fixture
def analyzer(system_info):
    return UserAnalyzer(system_info=system_info)


def test_nominal_no_config(analyzer, model_obj):
    # When no allowed_users config is provided, it should not run
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.NOT_RAN
    assert len(result.events) == 0


def test_nominal_with_config(analyzer, model_obj):
    # When all active users are allowed, it should pass
    args = UserAnalyzerArgs(allowed_users=["user1", "root"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_user_not_allowed(analyzer, model_obj):
    # If an active user is not allowed, it should error
    args = UserAnalyzerArgs(allowed_users=["foo"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.OS.value
        assert event.priority == EventPriority.CRITICAL
