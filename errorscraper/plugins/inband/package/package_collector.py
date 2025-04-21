import re
from typing import Callable

from pydantic import ValidationError

from errorscraper.base import InBandDataCollector
from errorscraper.connection.inband import CommandArtifact
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult
from errorscraper.utils import get_exception_details

from .packagedata import PackageDataModel


class PackageCollector(InBandDataCollector[PackageDataModel, None]):
    """Collecting Package information from the system"""

    DATA_MODEL = PackageDataModel

    def _detect_package_manager(self) -> Callable | None:
        package_manger_map: dict[str, Callable] = {
            "debian": self._debian_package_dump,
            "redhat": self._dump_fedora_centos_rhel_packages,
            "rhel": self._dump_fedora_centos_rhel_packages,
            "fedora": self._dump_fedora_centos_rhel_packages,
            "centos": self._dump_fedora_centos_rhel_packages,
            "arch": self._dump_arch_packages,
        }
        res = self._run_sut_cmd("cat /etc/*release")
        # search for the package manager key in the release file
        for os, package_manager in package_manger_map.items():
            package_search = re.findall(os, res.stdout, flags=re.IGNORECASE)
            if package_search:
                return package_manager
        return None

    def _windows_package_dump(self) -> dict[str, str]:
        MIN_SPLIT_LENGTH = 2
        res = self._run_sut_cmd("wmic product get name,version")
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
        MIN_SPLIT_LENGTH = 2
        MAX_SPLIT_LENGTH = 3
        res = self._run_sut_cmd("dpkg-query -W")
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
        MIN_SPLIT_LENGTH = 2
        MAX_SPLIT_LENGTH = 3
        res = self._run_sut_cmd("dnf list --installed")
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
        EXPECTED_SPLIT_LENGTH = 2
        res: CommandArtifact = self._run_sut_cmd("pacman -Q")
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

    def collect_data(self, args=None) -> tuple[TaskResult, PackageDataModel | None]:
        """Collect package information from the system.

        Package information includes all of the installed packages and their versions.
        For windows it will be collected using wmic and for linux it will be collected
        using the package manager of the system. The data is formatted into a dictionary
        with the package name as the key and the version as the value.

        Returns
        -------
        tuple[TaskResult, PackageDataModel | None]
            The task result and the package data model
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
