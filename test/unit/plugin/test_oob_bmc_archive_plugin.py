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
from unittest.mock import MagicMock

import pytest

from nodescraper.base import OOBSSHDataPlugin
from nodescraper.connection.inband.inband import BinaryFileArtifact, CommandArtifact
from nodescraper.connection.redfish import RedfishConnectionManager
from nodescraper.enums import ExecutionStatus, OSFamily, SystemLocation
from nodescraper.models import SystemInfo, TaskResult
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.ooband.bmc_archive import (
    BmcArchiveCollector,
    BmcArchiveCollectorArgs,
    OobBmcArchivePlugin,
    PathSpec,
)


@pytest.fixture
def collector(monkeypatch):
    monkeypatch.setattr(
        "nodescraper.base.inbandcollectortask.InBandDataCollector.__init__",
        lambda self, *args, **kwargs: None,
    )
    collector = BmcArchiveCollector(
        system_info=SystemInfo(
            hostname="bmc",
            location=SystemLocation.REMOTE,
            os_family=OSFamily.LINUX,
        ),
        connection=MagicMock(),
    )
    # InBandDataCollector.__init__ is stubbed, so Task/DataCollector init never runs.
    collector.parent = None
    collector.task_result_hooks = []
    collector.result = TaskResult(task=BmcArchiveCollector.__name__, parent=None)
    collector.result.status = ExecutionStatus.OK
    collector.result.message = ""
    collector.logger = MagicMock()
    return collector


def test_oob_bmc_archive_plugin_registers():
    assert OobBmcArchivePlugin.is_valid()
    assert OobBmcArchivePlugin.ANALYZER is None
    assert "OobBmcArchivePlugin" in PluginRegistry().plugins


def test_oob_bmc_archive_plugin_uses_redfish_connection_manager_like_oob_generic_collection():
    assert issubclass(OobBmcArchivePlugin, OOBSSHDataPlugin)
    assert OobBmcArchivePlugin.CONNECTION_TYPE is RedfishConnectionManager


def test_plugin_log_directory_name_uses_oob_prefix():
    from nodescraper.utils import pascal_to_snake

    assert pascal_to_snake("OobBmcArchivePlugin") == "oob_bmc_archive_plugin"


def test_tar_command_uses_streaming_tar_and_redirect(collector):
    cmd = collector._tar_command(
        "/data/example_a",
        "/tmp/node_scraper_archive_alpha.tar.gz",
        ignore_failed_read=True,
    )
    assert (
        cmd
        == "tar czf - --ignore-failed-read '/data/example_a' > '/tmp/node_scraper_archive_alpha.tar.gz'"
    )


def test_collect_path_omits_ignore_failed_read_when_tar_lacks_option(collector, monkeypatch):
    """If ``--ignore-failed-read`` is not supported, fall back to plain tar."""
    exists_result = CommandArtifact(
        command="test -e '/data/example_a'", stdout="", stderr="", exit_code=0
    )
    probe_unsupported = CommandArtifact(
        command="tar cf - --ignore-failed-read /dev/null",
        stdout="",
        stderr="tar: unrecognized option '--ignore-failed-read'\n",
        exit_code=1,
    )
    tar_plain = CommandArtifact(
        command="tar czf - '/data/example_a' > '/tmp/node_scraper_archive_alpha.tar.gz'",
        stdout="",
        stderr="",
        exit_code=0,
    )
    read_result = BinaryFileArtifact(filename="archive_alpha.tar.gz", contents=b"x")
    rm_result = CommandArtifact(command="rm -f", stdout="", stderr="", exit_code=0)

    collector._run_sut_cmd = MagicMock(
        side_effect=[exists_result, probe_unsupported, tar_plain, rm_result]
    )
    collector._read_sut_file = MagicMock(return_value=read_result)
    collector._log_event = MagicMock()

    path_spec = PathSpec(name="archive_alpha", path="/data/example_a")
    result, archive = collector._collect_path(
        path_spec,
        default_sudo=False,
        default_timeout=600,
        default_skip_if_missing=False,
        default_ignore_failed_read=True,
    )

    assert result.success is True
    assert archive is not None
    collector._run_sut_cmd.assert_any_call(
        "tar czf - '/data/example_a' > '/tmp/node_scraper_archive_alpha.tar.gz'",
        sudo=False,
        timeout=600,
        log_artifact=True,
    )


def test_collect_path_reads_archive_after_tar(collector, monkeypatch):
    exists_result = CommandArtifact(
        command="test -e '/data/example_a'", stdout="", stderr="", exit_code=0
    )
    probe_result = CommandArtifact(
        command="tar cf - --ignore-failed-read /dev/null",
        stdout="",
        stderr="",
        exit_code=0,
    )
    tar_result = CommandArtifact(
        command="tar czf - --ignore-failed-read '/data/example_a' > '/tmp/node_scraper_archive_alpha.tar.gz'",
        stdout="",
        stderr="",
        exit_code=0,
    )
    archive_bytes = b"fake-gzip-data"
    read_result = BinaryFileArtifact(filename="archive_alpha.tar.gz", contents=archive_bytes)
    rm_result = CommandArtifact(
        command="rm -f '/tmp/node_scraper_archive_alpha.tar.gz'",
        stdout="",
        stderr="",
        exit_code=0,
    )

    collector._run_sut_cmd = MagicMock(
        side_effect=[exists_result, probe_result, tar_result, rm_result]
    )
    collector._read_sut_file = MagicMock(return_value=read_result)
    collector._log_event = MagicMock()

    path_spec = PathSpec(name="archive_alpha", path="/data/example_a")
    result, archive = collector._collect_path(
        path_spec,
        default_sudo=False,
        default_timeout=600,
        default_skip_if_missing=False,
        default_ignore_failed_read=True,
    )

    assert result.success is True
    assert result.size_bytes == len(archive_bytes)
    assert archive is not None
    assert archive.filename == "archive_alpha.tar.gz"
    collector._run_sut_cmd.assert_any_call(
        "tar czf - --ignore-failed-read '/data/example_a' > '/tmp/node_scraper_archive_alpha.tar.gz'",
        sudo=False,
        timeout=600,
        log_artifact=True,
    )
    collector._read_sut_file.assert_called_once_with(
        "/tmp/node_scraper_archive_alpha.tar.gz",
        encoding=None,
        strip=False,
        log_artifact=True,
    )


def test_collect_path_skips_missing_path_when_configured(collector):
    missing_result = CommandArtifact(
        command="test -e '/data/missing'",
        stdout="",
        stderr="",
        exit_code=1,
    )
    collector._run_sut_cmd = MagicMock(return_value=missing_result)
    collector._log_event = MagicMock()

    path_spec = PathSpec(name="archive_missing", path="/data/missing")
    result, archive = collector._collect_path(
        path_spec,
        default_sudo=False,
        default_timeout=600,
        default_skip_if_missing=True,
        default_ignore_failed_read=True,
    )

    assert result.skipped is True
    assert result.success is False
    assert archive is None
    collector._run_sut_cmd.assert_called_once()


def test_collect_data_not_ran_without_paths(collector):
    collector._log_event = MagicMock()
    task_result, data = collector.collect_data(BmcArchiveCollectorArgs(paths=[]))

    assert task_result.status == ExecutionStatus.NOT_RAN
    assert data is None
    assert "collection_args.paths" in task_result.message


def test_collect_data_reports_partial_failures(collector, monkeypatch):
    exists_ok = CommandArtifact(command="test -e", stdout="", stderr="", exit_code=0)
    probe_ok = CommandArtifact(
        command="tar cf - --ignore-failed-read /dev/null", stdout="", stderr="", exit_code=0
    )
    ok_tar = CommandArtifact(command="tar", stdout="", stderr="", exit_code=0)
    fail_tar = CommandArtifact(command="tar", stdout="", stderr="missing", exit_code=2)
    no_archive = CommandArtifact(command="test -s", stdout="", stderr="", exit_code=1)
    rm = CommandArtifact(command="rm", stdout="", stderr="", exit_code=0)
    archive = BinaryFileArtifact(filename="archive_alpha.tar.gz", contents=b"data")

    collector._run_sut_cmd = MagicMock(
        side_effect=[
            exists_ok,
            probe_ok,
            ok_tar,
            rm,
            exists_ok,
            fail_tar,
            no_archive,
            rm,
        ]
    )
    collector._read_sut_file = MagicMock(return_value=archive)
    collector._log_event = MagicMock()

    args = BmcArchiveCollectorArgs(
        paths=[
            PathSpec(name="archive_alpha", path="/data/example_a"),
            PathSpec(name="archive_beta", path="/data/example_b"),
        ]
    )
    task_result, data = collector.collect_data(args)

    assert task_result.status == ExecutionStatus.ERROR
    assert data is not None
    assert len(data.archives) == 1
    assert data.results[0].success is True
    assert data.results[1].success is False
