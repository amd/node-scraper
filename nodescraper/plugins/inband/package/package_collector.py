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
import re
from typing import Callable, Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import get_exception_details

from .packagedata import PackageDataModel


class PackageCollector(InBandDataCollector[PackageDataModel, None]):
    """Collecting Package information from the system"""

    DATA_MODEL = PackageDataModel
    CMD_WINDOWS = "wmic product get name,version"
    CMD_RELEASE = "cat /etc/*release"
    CMD_DPKG = "dpkg-query -W"
    CMD_DNF = "dnf list --installed"
    CMD_PACMAN = "pacman -Q"

    def _detect_package_manager(self) -> Optional[Callable]:
        """Detect the package manager based on the OS release information.

        Returns:
            Optional[Callable]: A callable function that dumps the packages for the detected package manager,
            or None if the package manager is not supported.
        """
        package_manger_map: dict[str, Callable] = {
            "debian": self._debian_package_dump,
            "redhat": self._dump_fedora_centos_rhel_packages,
            "rhel": self._dump_fedora_centos_rhel_packages,
            "fedora": self._dump_fedora_centos_rhel_packages,
            "centos": self._dump_fedora_centos_rhel_packages,
            "arch": self._dump_arch_packages,
        }
        res = self._run_sut_cmd(self.CMD_RELEASE)
        # search for the package manager key in the release file
        for os, package_manager in package_manger_map.items():
            package_search = re.findall(os, res.stdout, flags=re.IGNORECASE)
            if package_search:
                return package_manager
        return None

    def _windows_package_dump(self) -> dict[str, str]:
        """Dump installed packages on Windows using wmic

        Returns:
            dict[str, str]: A dictionary with package names as keys and their versions as values.
        """
        MIN_SPLIT_LENGTH = 2
        res = self._run_sut_cmd(self.CMD_WINDOWS)
        packages = {}
        if res.exit_code != 0:
            self._handle_command_failure(res)
            return {}
        lines = res.stdout.splitlines()

        for line in lines[1:]:
            columns = line.split()
            if len(columns) <= MIN_SPLIT_LENGTH:
                continue
            # spaces are allowed in names, so we need to join them
            name = (" ").join(columns[:-1])
            version = columns[-1]
            packages[name] = version

        return packages

    def _debian_package_dump(self) -> dict[str, str]:
        """Dump installed packages on Debian-based systems using dpkg-query

        Returns:
            dict[str, str]: A dictionary with package names as keys and their versions as values.
        """
        MIN_SPLIT_LENGTH = 2
        MAX_SPLIT_LENGTH = 3
        res = self._run_sut_cmd(self.CMD_DPKG)
        packages = {}
        if res.exit_code != 0:
            self._handle_command_failure(res)
            return {}

        lines = res.stdout.splitlines()
        for line in lines:
            columns = line.split()
            if len(columns) < MIN_SPLIT_LENGTH or len(columns) > MAX_SPLIT_LENGTH:
                continue
            if columns[0] == "Installed" or columns[1] == "Packages":
                continue
            packages[columns[0]] = columns[1]
        return packages

    def _dump_fedora_centos_rhel_packages(self) -> dict[str, str]:
        """Dump installed packages on Fedora, CentOS, or RHEL using dnf

        Returns:
            dict[str, str]: A dictionary with package names as keys and their versions as values.
        """
        MIN_SPLIT_LENGTH = 2
        MAX_SPLIT_LENGTH = 3
        res = self._run_sut_cmd(self.CMD_DNF)
        packages = {}
        if res.exit_code != 0:
            self._handle_command_failure(res)
            return {}
        lines = res.stdout.splitlines()
        for line in lines:
            columns = line.split()
            if len(columns) < MIN_SPLIT_LENGTH or len(columns) > MAX_SPLIT_LENGTH:
                continue
            if "Installed" in columns[0] or "Packages" in columns[1]:
                continue
            packages[columns[0]] = columns[1]
        return packages

    def _dump_arch_packages(self) -> dict[str, str]:
        """Dump installed packages on Arch Linux using pacman

        Returns:
            dict[str, str]: A dictionary with package names as keys and their versions as values.
        """
        EXPECTED_SPLIT_LENGTH = 2
        res: CommandArtifact = self._run_sut_cmd(self.CMD_PACMAN)
        packages = {}
        if res.exit_code != 0:
            self._handle_command_failure(res)
            return {}
        lines = res.stdout.splitlines()
        for line in lines:
            columns = line.split()
            if len(columns) != EXPECTED_SPLIT_LENGTH:
                continue
            packages[columns[0]] = columns[1]
        return packages

    def _handle_command_failure(self, command_artifact: CommandArtifact):
        """Handle command failure by logging the error and updating the result.
        This method logs the error details and updates the result with a failure status.

        Args:
            command_artifact (CommandArtifact): The command artifact containing the command output and error details.
        """
        self._log_event(
            category=EventCategory.OS,
            description=f"Error running command: {command_artifact.command}",
            priority=EventPriority.WARNING,
            data={
                "stderr": command_artifact.stderr,
                "exit_code": command_artifact.exit_code,
            },
        )
        self.result.message = "Failed to run Package Manager command"
        self.result.status = ExecutionStatus.EXECUTION_FAILURE

    def collect_data(self, args=None) -> tuple[TaskResult, Optional[PackageDataModel]]:
        """Collect package information from the system.

        Returns:
            tuple[TaskResult, Optional[PackageDataModel]]: tuple containing the task result and a PackageDataModel instance
            with the collected package information, or None if there was an error.
        """
        packages = {}
        # Windows
        if self.system_info.os_family == OSFamily.WINDOWS:
            packages = self._windows_package_dump()
        # Linux
        elif self.system_info.os_family == OSFamily.LINUX:
            package_manager = self._detect_package_manager()
            if package_manager:
                packages = package_manager()
            else:
                self.result.message = "Unsupported package manager"
                self.result.status = ExecutionStatus.NOT_RAN
                return self.result, None
        else:
            self.result.message = "Unsupported OS"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None
        try:
            package_model = PackageDataModel(version_info=packages)
        except ValidationError as val_err:
            self._log_event(
                category=EventCategory.RUNTIME,
                description="Error validating package data",
                priority=EventPriority.WARNING,
                data=get_exception_details(val_err),
            )
            package_model = None

        return self.result, package_model
