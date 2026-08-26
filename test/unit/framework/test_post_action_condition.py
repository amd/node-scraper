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
"""Unit tests for PostActionCondition matching logic."""
import pytest

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.models import DataPluginResult, Event, PluginResult, TaskResult
from nodescraper.models.postactioncondition import PostActionCondition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    category: str,
    description: str,
    priority: EventPriority = EventPriority.ERROR,
) -> Event:
    return Event(
        category=category,
        description=description,
        priority=priority,
        reporter="test",
    )


def _make_result(
    source: str = "SomePlugin",
    status: ExecutionStatus = ExecutionStatus.OK,
    analysis_events: list[Event] | None = None,
    collection_events: list[Event] | None = None,
) -> PluginResult:
    """Build a PluginResult with optional events in analysis and/or collection results."""
    return PluginResult(
        status=status,
        source=source,
        result_data=DataPluginResult(
            analysis_result=TaskResult(status=status, events=analysis_events or []),
            collection_result=TaskResult(status=status, events=collection_events or []),
        ),
    )


# ---------------------------------------------------------------------------
# No-field conditions (vacuously true)
# ---------------------------------------------------------------------------


def test_no_fields_matches_any_result():
    """A condition with all fields None matches any result."""
    condition = PostActionCondition()
    result = _make_result(status=ExecutionStatus.OK)
    assert condition.is_met([result]) is True


def test_no_fields_matches_error_result():
    condition = PostActionCondition()
    result = _make_result(status=ExecutionStatus.ERROR)
    assert condition.is_met([result]) is True


def test_no_results_returns_false():
    """With an empty results list there are no candidates — always False."""
    condition = PostActionCondition()
    assert condition.is_met([]) is False


# ---------------------------------------------------------------------------
# status field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition_status, result_status, expected",
    [
        ("WARNING", ExecutionStatus.WARNING, True),  # exact match at threshold
        ("WARNING", ExecutionStatus.ERROR, True),  # above threshold
        ("WARNING", ExecutionStatus.EXECUTION_FAILURE, True),
        ("ERROR", ExecutionStatus.ERROR, True),
        ("ERROR", ExecutionStatus.OK, False),  # below threshold
        ("ERROR", ExecutionStatus.WARNING, False),
        ("EXECUTION_FAILURE", ExecutionStatus.ERROR, False),
        ("OK", ExecutionStatus.OK, True),
        ("OK", ExecutionStatus.WARNING, True),
    ],
)
def test_status_threshold(condition_status, result_status, expected):
    condition = PostActionCondition(status=condition_status)
    result = _make_result(status=result_status)
    assert condition.is_met([result]) is expected


def test_status_invalid_name_returns_false():
    """An unrecognised status name never matches (doesn't raise)."""
    condition = PostActionCondition(status="NONEXISTENT_STATUS")
    result = _make_result(status=ExecutionStatus.ERROR)
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# event_category field
# ---------------------------------------------------------------------------


def test_event_category_matches_analysis_event():
    condition = PostActionCondition(event_category="WIDGET_ERROR")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault detected")],
    )
    assert condition.is_met([result]) is True


def test_event_category_matches_collection_event():
    """event_category also matches events from collection_result."""
    condition = PostActionCondition(event_category="COLLECTION_WARN")
    result = _make_result(
        status=ExecutionStatus.WARNING,
        collection_events=[_make_event("COLLECTION_WARN", "something", EventPriority.WARNING)],
    )
    assert condition.is_met([result]) is True


def test_event_category_no_match():
    condition = PostActionCondition(event_category="WIDGET_ERROR")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("GIZMO_ERROR", "gizmo fault")],
    )
    assert condition.is_met([result]) is False


def test_event_category_normalisation():
    """Category matching normalises spaces and hyphens to underscores and uppercases."""
    condition = PostActionCondition(event_category="widget-error")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault")],
    )
    assert condition.is_met([result]) is True


def test_event_category_no_events_returns_false():
    condition = PostActionCondition(event_category="WIDGET_ERROR")
    result = _make_result(status=ExecutionStatus.ERROR)  # no events
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# event_priority field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition_priority, event_priority, expected",
    [
        ("WARNING", EventPriority.WARNING, True),
        ("WARNING", EventPriority.ERROR, True),
        ("WARNING", EventPriority.CRITICAL, True),
        ("ERROR", EventPriority.ERROR, True),
        ("ERROR", EventPriority.CRITICAL, True),
        ("ERROR", EventPriority.WARNING, False),
        ("CRITICAL", EventPriority.ERROR, False),
        ("CRITICAL", EventPriority.CRITICAL, True),
    ],
)
def test_event_priority_threshold(condition_priority, event_priority, expected):
    condition = PostActionCondition(event_priority=condition_priority)
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("SOME_CAT", "some description", event_priority)],
    )
    assert condition.is_met([result]) is expected


def test_event_priority_invalid_name_returns_false():
    condition = PostActionCondition(event_priority="SUPER_CRITICAL")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("CAT", "desc", EventPriority.CRITICAL)],
    )
    assert condition.is_met([result]) is False


def test_event_priority_no_events_returns_false():
    condition = PostActionCondition(event_priority="WARNING")
    result = _make_result(status=ExecutionStatus.ERROR)
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# event_description_contains field
# ---------------------------------------------------------------------------


def test_event_description_contains_match():
    condition = PostActionCondition(event_description_contains="widget fault")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault detected on unit 0")],
    )
    assert condition.is_met([result]) is True


def test_event_description_contains_no_match():
    condition = PostActionCondition(event_description_contains="widget fault")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("GIZMO_ERROR", "gizmo fault")],
    )
    assert condition.is_met([result]) is False


def test_event_description_contains_case_sensitive():
    """Substring match is case-sensitive."""
    condition = PostActionCondition(event_description_contains="Widget Fault")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault detected")],
    )
    assert condition.is_met([result]) is False


def test_event_description_contains_no_events_returns_false():
    condition = PostActionCondition(event_description_contains="anything")
    result = _make_result(status=ExecutionStatus.ERROR)
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# AND semantics within a single condition
# ---------------------------------------------------------------------------


def test_and_semantics_status_matches_category_does_not():
    """Both fields specified; status matches but category doesn't → False."""
    condition = PostActionCondition(status="ERROR", event_category="WIDGET_ERROR")
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("GIZMO_ERROR", "gizmo fault")],
    )
    assert condition.is_met([result]) is False


def test_and_semantics_category_matches_status_does_not():
    """Both fields specified; category matches but status doesn't → False."""
    condition = PostActionCondition(status="ERROR", event_category="WIDGET_ERROR")
    result = _make_result(
        status=ExecutionStatus.WARNING,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault")],
    )
    assert condition.is_met([result]) is False


def test_and_semantics_all_fields_match():
    """All four fields specified and all matched → True."""
    condition = PostActionCondition(
        status="WARNING",
        event_category="WIDGET_ERROR",
        event_priority="ERROR",
        event_description_contains="widget fault",
    )
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "widget fault detected", EventPriority.ERROR)],
    )
    assert condition.is_met([result]) is True


def test_and_semantics_three_fields_one_missing():
    """Three fields specified; the one unmatched field causes False."""
    condition = PostActionCondition(
        status="ERROR",
        event_category="WIDGET_ERROR",
        event_description_contains="widget fault",
    )
    result = _make_result(
        status=ExecutionStatus.ERROR,
        analysis_events=[_make_event("WIDGET_ERROR", "gizmo fault")],  # description doesn't match
    )
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# plugin filter
# ---------------------------------------------------------------------------


def test_plugin_filter_restricts_to_named_source():
    """With plugin set, only that plugin's result is a candidate."""
    condition = PostActionCondition(plugin="PluginA", status="ERROR")
    result_a = _make_result(source="PluginA", status=ExecutionStatus.ERROR)
    result_b = _make_result(source="PluginB", status=ExecutionStatus.ERROR)
    assert condition.is_met([result_a, result_b]) is True


def test_plugin_filter_excludes_other_source():
    """Named plugin's result doesn't meet the condition; other results are excluded."""
    condition = PostActionCondition(plugin="PluginA", status="ERROR")
    result_a = _make_result(source="PluginA", status=ExecutionStatus.OK)
    result_b = _make_result(source="PluginB", status=ExecutionStatus.ERROR)
    assert condition.is_met([result_a, result_b]) is False


def test_plugin_filter_none_checks_all_results():
    """With plugin=None, any result may satisfy the condition."""
    condition = PostActionCondition(plugin=None, status="ERROR")
    result_a = _make_result(source="PluginA", status=ExecutionStatus.OK)
    result_b = _make_result(source="PluginB", status=ExecutionStatus.ERROR)
    assert condition.is_met([result_a, result_b]) is True


def test_plugin_filter_named_plugin_not_in_results():
    """Named plugin not present in results at all → no candidates → False."""
    condition = PostActionCondition(plugin="MissingPlugin", status="ERROR")
    result = _make_result(source="OtherPlugin", status=ExecutionStatus.ERROR)
    assert condition.is_met([result]) is False


# ---------------------------------------------------------------------------
# result_data edge cases
# ---------------------------------------------------------------------------


def test_result_with_no_result_data_status_only():
    """A bare PluginResult (no result_data) can still match on status."""
    condition = PostActionCondition(status="ERROR")
    result = PluginResult(status=ExecutionStatus.ERROR, source="BarePlugin")
    assert condition.is_met([result]) is True


def test_result_with_no_result_data_event_field_returns_false():
    """A bare PluginResult has no events; event-based conditions are False."""
    condition = PostActionCondition(event_category="WIDGET_ERROR")
    result = PluginResult(status=ExecutionStatus.ERROR, source="BarePlugin")
    assert condition.is_met([result]) is False
