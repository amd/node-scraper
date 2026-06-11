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
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband.inband import BaseFileArtifact, BinaryFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import shell_quote

from .bmc_archive_data import ArchiveCollectionResult, BmcArchiveDataModel
from .collector_args import BmcArchiveCollectorArgs, PathSpec


class BmcArchiveCollector(InBandDataCollector[BmcArchiveDataModel, BmcArchiveCollectorArgs]):
    """Archive BMC directories over SSH using tar czf - <path>."""

    DATA_MODEL = BmcArchiveDataModel
    SUPPORTED_OS_FAMILY = {OSFamily.LINUX, OSFamily.UNKNOWN}

    REMOTE_ARCHIVE_TEMPLATE = "/tmp/node_scraper_{name}.tar.gz"
    # None until first probe in a run; collect_data resets so each collection re-probes.
    _tar_ignore_failed_read_supported: Optional[bool] = None

    def _remote_archive_path(self, name: str) -> str:
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
        return self.REMOTE_ARCHIVE_TEMPLATE.format(name=safe_name)

    def _remote_tar_supports_ignore_failed_read(self, *, sudo: bool, timeout: int) -> bool:
        """Return True only if remote tar accepts GNU's --ignore-failed-read."""
        cached = getattr(self, "_tar_ignore_failed_read_supported", None)
        if cached is not None:
            return cached
        probe = self._run_sut_cmd(
            "tar cf - --ignore-failed-read /dev/null",
            sudo=sudo,
            timeout=min(timeout, 60),
            log_artifact=False,
        )
        stderr = (probe.stderr or "").lower()
        if probe.exit_code == 0:
            self._tar_ignore_failed_read_supported = True
            return True
        if any(
            phrase in stderr
            for phrase in (
                "unrecognized option",
                "invalid option",
                "unknown option",
                "illegal option",
            )
        ):
            self._tar_ignore_failed_read_supported = False
            return False
        # Unrecognized failure: omit the flag so archiving still runs.
        self._tar_ignore_failed_read_supported = False
        return False

    def _tar_command(
        self,
        path: str,
        remote_archive: str,
        *,
        ignore_failed_read: bool,
    ) -> str:
        tar_flags = "czf -"
        if ignore_failed_read:
            tar_flags = "czf - --ignore-failed-read"
        return f"tar {tar_flags} {shell_quote(path)} > {shell_quote(remote_archive)}"

    def _path_exists(self, path: str, *, sudo: bool, timeout: int) -> bool:
        res = self._run_sut_cmd(
            f"test -e {shell_quote(path)}",
            sudo=sudo,
            timeout=timeout,
            log_artifact=False,
        )
        return res.exit_code == 0

    def _remote_archive_has_content(self, remote_archive: str, *, sudo: bool, timeout: int) -> bool:
        res = self._run_sut_cmd(
            f"test -s {shell_quote(remote_archive)}",
            sudo=sudo,
            timeout=timeout,
            log_artifact=False,
        )
        return res.exit_code == 0

    def _read_remote_archive(
        self,
        path_spec: PathSpec,
        *,
        remote_archive: str,
        archive_filename: str,
        sudo: bool,
        timeout: int,
        result: ArchiveCollectionResult,
    ) -> tuple[ArchiveCollectionResult, Optional[BinaryFileArtifact]]:
        read_artifact: Optional[BaseFileArtifact] = None
        try:
            read_artifact = self._read_sut_file(
                remote_archive,
                encoding=None,
                strip=False,
                log_artifact=True,
            )
        except Exception as exc:
            result.stderr = str(exc)
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"BMC archive read failed: {path_spec.name}",
                data={"name": path_spec.name, "path": path_spec.path, "error": str(exc)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return result, None
        finally:
            self._run_sut_cmd(
                f"rm -f {shell_quote(remote_archive)}",
                sudo=sudo,
                timeout=timeout,
                log_artifact=False,
            )

        if not isinstance(read_artifact, BinaryFileArtifact) or not read_artifact.contents:
            result.stderr = "Archive file was empty or unreadable"
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"BMC archive empty: {path_spec.name}",
                data={"name": path_spec.name, "path": path_spec.path},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return result, None

        read_artifact.filename = archive_filename
        result.success = True
        result.size_bytes = len(read_artifact.contents)
        return result, read_artifact

    def _collect_path(
        self,
        path_spec: PathSpec,
        *,
        default_sudo: bool,
        default_timeout: int,
        default_skip_if_missing: bool,
        default_ignore_failed_read: bool,
    ) -> tuple[ArchiveCollectionResult, Optional[BinaryFileArtifact]]:
        sudo = default_sudo if path_spec.sudo is None else path_spec.sudo
        timeout = default_timeout if path_spec.timeout is None else path_spec.timeout
        skip_if_missing = (
            default_skip_if_missing
            if path_spec.skip_if_missing is None
            else path_spec.skip_if_missing
        )
        ignore_failed_read = (
            default_ignore_failed_read
            if path_spec.ignore_failed_read is None
            else path_spec.ignore_failed_read
        )
        remote_archive = self._remote_archive_path(path_spec.name)
        archive_filename = f"{path_spec.name}.tar.gz"

        result = ArchiveCollectionResult(
            name=path_spec.name,
            path=path_spec.path,
            archive_filename=archive_filename,
        )

        if not self._path_exists(path_spec.path, sudo=sudo, timeout=timeout):
            result.stderr = f"Path does not exist: {path_spec.path}"
            if skip_if_missing:
                result.skipped = True
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"BMC archive skipped: {path_spec.name}",
                    data={"name": path_spec.name, "path": path_spec.path, "reason": "missing"},
                    priority=EventPriority.WARNING,
                )
                return result, None

            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"BMC archive failed: {path_spec.name}",
                data={
                    "name": path_spec.name,
                    "path": path_spec.path,
                    "exit_code": 2,
                    "stderr": result.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            result.exit_code = 2
            return result, None

        use_ignore_failed_read = (
            ignore_failed_read
            and self._remote_tar_supports_ignore_failed_read(sudo=sudo, timeout=timeout)
        )

        tar_res = self._run_sut_cmd(
            self._tar_command(
                path_spec.path,
                remote_archive,
                ignore_failed_read=use_ignore_failed_read,
            ),
            sudo=sudo,
            timeout=timeout,
            log_artifact=True,
        )
        result.exit_code = tar_res.exit_code
        result.stderr = tar_res.stderr or ""

        if tar_res.exit_code != 0:
            if not self._remote_archive_has_content(
                remote_archive,
                sudo=sudo,
                timeout=timeout,
            ):
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"BMC archive failed: {path_spec.name}",
                    data={
                        "name": path_spec.name,
                        "path": path_spec.path,
                        "exit_code": tar_res.exit_code,
                        "stderr": tar_res.stderr,
                    },
                    priority=EventPriority.ERROR,
                    console_log=True,
                )
                self._run_sut_cmd(
                    f"rm -f {shell_quote(remote_archive)}",
                    sudo=sudo,
                    timeout=timeout,
                    log_artifact=False,
                )
                return result, None

            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"BMC archive partial: {path_spec.name}",
                data={
                    "name": path_spec.name,
                    "path": path_spec.path,
                    "exit_code": tar_res.exit_code,
                    "stderr": tar_res.stderr,
                },
                priority=EventPriority.WARNING,
            )

        result, archive_artifact = self._read_remote_archive(
            path_spec,
            remote_archive=remote_archive,
            archive_filename=archive_filename,
            sudo=sudo,
            timeout=timeout,
            result=result,
        )
        if result.success:
            priority = EventPriority.WARNING if tar_res.exit_code != 0 else EventPriority.INFO
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"BMC archive collected: {path_spec.name}",
                data={
                    "name": path_spec.name,
                    "path": path_spec.path,
                    "size_bytes": result.size_bytes,
                    "archive_filename": archive_filename,
                    "partial": tar_res.exit_code != 0,
                },
                priority=priority,
            )
        return result, archive_artifact

    def collect_data(
        self,
        args: Optional[BmcArchiveCollectorArgs] = None,
    ) -> tuple[TaskResult, Optional[BmcArchiveDataModel]]:
        if args is None:
            args = BmcArchiveCollectorArgs()

        if not args.paths:
            self.result.message = "No paths configured in collection_args.paths"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        self._tar_ignore_failed_read_supported = None

        results: list[ArchiveCollectionResult] = []
        archives: list[BinaryFileArtifact] = []
        failures: list[str] = []

        for path_spec in args.paths:
            result, archive_artifact = self._collect_path(
                path_spec,
                default_sudo=args.sudo,
                default_timeout=args.timeout,
                default_skip_if_missing=args.skip_if_missing,
                default_ignore_failed_read=args.ignore_failed_read,
            )
            results.append(result)
            if archive_artifact is not None:
                archives.append(archive_artifact)
            if not result.success and not result.skipped:
                failures.append(path_spec.name)

        success_count = sum(1 for result in results if result.success)
        skipped_count = sum(1 for result in results if result.skipped)
        total = len(results)

        if failures:
            self.result.message = (
                f"BMC archive collection: {success_count}/{total} paths archived "
                f"({len(failures)} errors: {', '.join(failures)}"
                f"{f'; {skipped_count} skipped' if skipped_count else ''})"
            )
            self.result.status = ExecutionStatus.ERROR
        else:
            suffix = f", {skipped_count} skipped" if skipped_count else ""
            self.result.message = (
                f"BMC archive collection: {success_count}/{total} paths archived{suffix}"
            )
            self.result.status = ExecutionStatus.OK

        return self.result, BmcArchiveDataModel(results=results, archives=archives)
