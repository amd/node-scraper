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
"""Unit tests for PostActionPluginConfig.should_run OR semantics."""
from typing import Union

from nodescraper.enums import ExecutionStatus
from nodescraper.models import PluginResult
from nodescraper.models.postactioncondition import PostActionCondition
from nodescraper.models.postactionpluginconfig import PostActionPluginConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(source: str, status: ExecutionStatus) -> PluginResult:
    return PluginResult(status=status, source=source)


def _cond(status: str, plugin: Union[str, None] = None) -> PostActionCondition:
    """Shorthand: a condition that fires when *source* has at least *status*."""
    return PostActionCondition(plugin=plugin, status=status)


# ---------------------------------------------------------------------------
# Empty conditions
# ---------------------------------------------------------------------------


def test_no_conditions_never_fires():
    """An empty conditions list always returns False — no accidental unconditional runs."""
    cfg = PostActionPluginConfig(plugin="SomePlugin", conditions=[])
    results = [_make_result("Primary", ExecutionStatus.EXECUTION_FAILURE)]
    assert cfg.should_run(results) is False


def test_no_conditions_empty_results_also_false():
    cfg = PostActionPluginConfig(plugin="SomePlugin", conditions=[])
    assert cfg.should_run([]) is False


# ---------------------------------------------------------------------------
# OR semantics across conditions
# ---------------------------------------------------------------------------


def test_or_first_condition_met_second_not():
    """should_run is True when the first condition fires even if the second doesn't."""
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[
            _cond("ERROR", plugin="PluginA"),  # PluginA has ERROR → True
            _cond("ERROR", plugin="PluginB"),  # PluginB has OK → False
        ],
    )
    results = [
        _make_result("PluginA", ExecutionStatus.ERROR),
        _make_result("PluginB", ExecutionStatus.OK),
    ]
    assert cfg.should_run(results) is True


def test_or_first_condition_not_met_second_met():
    """should_run is True when only the second condition fires."""
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[
            _cond("ERROR", plugin="PluginA"),  # PluginA has OK → False
            _cond("ERROR", plugin="PluginB"),  # PluginB has ERROR → True
        ],
    )
    results = [
        _make_result("PluginA", ExecutionStatus.OK),
        _make_result("PluginB", ExecutionStatus.ERROR),
    ]
    assert cfg.should_run(results) is True


def test_or_no_conditions_met():
    """should_run is False when no condition is satisfied."""
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[
            _cond("ERROR", plugin="PluginA"),
            _cond("ERROR", plugin="PluginB"),
        ],
    )
    results = [
        _make_result("PluginA", ExecutionStatus.OK),
        _make_result("PluginB", ExecutionStatus.WARNING),
    ]
    assert cfg.should_run(results) is False


def test_or_all_conditions_met():
    """should_run is True when every condition is satisfied (OR short-circuits at first)."""
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[
            _cond("ERROR", plugin="PluginA"),
            _cond("ERROR", plugin="PluginB"),
        ],
    )
    results = [
        _make_result("PluginA", ExecutionStatus.ERROR),
        _make_result("PluginB", ExecutionStatus.ERROR),
    ]
    assert cfg.should_run(results) is True


def test_single_condition_met():
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[_cond("WARNING")],
    )
    results = [_make_result("Primary", ExecutionStatus.ERROR)]
    assert cfg.should_run(results) is True


def test_single_condition_not_met():
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[_cond("ERROR")],
    )
    results = [_make_result("Primary", ExecutionStatus.OK)]
    assert cfg.should_run(results) is False


# ---------------------------------------------------------------------------
# Empty results list
# ---------------------------------------------------------------------------


def test_conditions_present_empty_results_returns_false():
    """Conditions exist but there are no primary results to match against."""
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        conditions=[_cond("ERROR")],
    )
    assert cfg.should_run([]) is False


# ---------------------------------------------------------------------------
# plugin_args field validation
# ---------------------------------------------------------------------------


def test_plugin_args_defaults_to_empty_dict():
    cfg = PostActionPluginConfig(plugin="SomePlugin", conditions=[_cond("ERROR")])
    assert cfg.plugin_args == {}


def test_plugin_args_passed_through():
    cfg = PostActionPluginConfig(
        plugin="SomePlugin",
        plugin_args={"collection": True, "analysis": False},
        conditions=[_cond("ERROR")],
    )
    assert cfg.plugin_args == {"collection": True, "analysis": False}


# ---------------------------------------------------------------------------
# JSON round-trip (Pydantic model_validate from dict)
# ---------------------------------------------------------------------------


def test_model_validate_from_dict():
    """PostActionPluginConfig can be constructed from a plain dict (as from JSON config)."""
    raw = {
        "plugin": "RemediationPlugin",
        "plugin_args": {"collection": True},
        "conditions": [
            {"plugin": "PrimaryPlugin", "status": "ERROR"},
            {"event_priority": "CRITICAL", "event_description_contains": "widget fault"},
        ],
    }
    cfg = PostActionPluginConfig.model_validate(raw)
    assert cfg.plugin == "RemediationPlugin"
    assert cfg.plugin_args == {"collection": True}
    assert len(cfg.conditions) == 2
    assert cfg.conditions[0].plugin == "PrimaryPlugin"
    assert cfg.conditions[0].status == "ERROR"
    assert cfg.conditions[1].event_priority == "CRITICAL"
    assert cfg.conditions[1].event_description_contains == "widget fault"
