###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from types import SimpleNamespace

import pytest

from nodescraper.enums import ExecutionStatus, OSFamily
from nodescraper.plugins.inband.sys_settings.sys_settings_collector import (
    SysSettingsCollector,
)
from nodescraper.plugins.inband.sys_settings.sys_settings_data import (
    SysSettingsDataModel,
)

SYSFS_BASE = "/sys/kernel/mm/transparent_hugepage"
PATH_ENABLED = f"{SYSFS_BASE}/enabled"
PATH_DEFRAG = f"{SYSFS_BASE}/defrag"


@pytest.fixture
def linux_sys_settings_collector(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    return SysSettingsCollector(system_info=system_info, connection=conn_mock)


@pytest.fixture
def collection_args():
    return {"paths": [PATH_ENABLED, PATH_DEFRAG]}


def make_artifact(exit_code, stdout):
    return SimpleNamespace(command="", exit_code=exit_code, stdout=stdout, stderr="")


def test_collect_data_success(linux_sys_settings_collector, collection_args):
    """Both enabled and defrag read successfully."""

    def run_cmd(cmd, **kwargs):
        if "enabled" in cmd:
            return make_artifact(0, "[always] madvise never")
        return make_artifact(0, "[madvise] always never defer")

    linux_sys_settings_collector._run_sut_cmd = run_cmd
    result, data = linux_sys_settings_collector.collect_data(collection_args)

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert isinstance(data, SysSettingsDataModel)
    assert data.readings.get(PATH_ENABLED) == "always"
    assert data.readings.get(PATH_DEFRAG) == "madvise"
    assert "Sysfs collected 2 path(s)" in result.message


def test_collect_data_no_paths_not_ran(linux_sys_settings_collector):
    """No paths in args -> NOT_RAN."""
    result, data = linux_sys_settings_collector.collect_data({})
    assert result.status == ExecutionStatus.NOT_RAN
    assert "No paths configured" in result.message
    assert data is None


def test_collect_data_enabled_fails(linux_sys_settings_collector, collection_args):
    """Enabled read fails; defrag succeeds -> still get partial data."""

    def run_cmd(cmd, **kwargs):
        if "enabled" in cmd:
            return make_artifact(1, "")
        return make_artifact(0, "[never] always madvise")

    linux_sys_settings_collector._run_sut_cmd = run_cmd
    result, data = linux_sys_settings_collector.collect_data(collection_args)

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert PATH_ENABLED not in data.readings
    assert data.readings.get(PATH_DEFRAG) == "never"


def test_collect_data_both_fail(linux_sys_settings_collector, collection_args):
    """Both reads fail -> error."""

    def run_cmd(cmd, **kwargs):
        return make_artifact(1, "")

    linux_sys_settings_collector._run_sut_cmd = run_cmd
    result, data = linux_sys_settings_collector.collect_data(collection_args)

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "Sysfs settings not read" in result.message


def test_collector_raises_on_non_linux(system_info, conn_mock):
    """SysSettingsCollector does not support non-Linux; constructor raises."""
    from nodescraper.interfaces.task import SystemCompatibilityError

    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError, match="not supported"):
        SysSettingsCollector(system_info=system_info, connection=conn_mock)
