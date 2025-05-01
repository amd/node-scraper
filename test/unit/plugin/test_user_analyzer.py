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
