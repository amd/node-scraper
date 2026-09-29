# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

import pytest

from nodescraper.interfaces.task import Task


def test_task_subclass_with_task_type_is_allowed():
    """Baseline: a subclass that declares TASK_TYPE is created without error."""

    class GoodTask(Task):
        TASK_TYPE = "GOOD_TASK"

    assert GoodTask.TASK_TYPE == "GOOD_TASK"


def test_task_subclass_with_none_task_type_raises():
    """Baseline: TASK_TYPE explicitly set to None is rejected."""

    with pytest.raises(TypeError):

        class NoneTask(Task):
            TASK_TYPE = None


def test_task_subclass_without_task_type_raises_type_error():
    """A subclass that never declares TASK_TYPE must raise the documented TypeError."""

    with pytest.raises(TypeError):

        class MissingTaskType(Task):
            pass
