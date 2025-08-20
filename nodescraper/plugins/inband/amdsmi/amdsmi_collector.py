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
import io
import json
import re
from typing import TypeVar

from packaging.version import Version as PackageVersion
from pydantic import BaseModel, ValidationError

from nodescraper.base.inbandcollectortask import InBandDataCollector
from nodescraper.connection.inband.inband import BaseFileArtifact, CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models import TaskResult
from nodescraper.models.datamodel import FileModel
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiData,
    AmdSmiListItem,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiTstData,
    AmdSmiVersion,
    BadPages,
    Fw,
    Partition,
    Processes,
    Topo,
    XgmiLinks,
    XgmiMetrics,
)
from nodescraper.utils import get_exception_details, get_exception_traceback

T = TypeVar("T", bound=BaseModel)


class AmdSmiCollector(InBandDataCollector[AmdSmiData, None]):
    """class for collection of inband tool amd-smi data."""

    AMD_SMI_EXE = "amd-smi"

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AmdSmiData

    def _check_amdsmi_installed(self) -> bool:
        """Return if amd-smi is installed"""

        cmd_ret: CommandArtifact = self._run_system_command("which amd-smi")
        return bool(cmd_ret.exit_code == 0 and "no amd-smi in" not in cmd_ret.stdout)

    def _check_command_supported(self, command: str) -> bool:
        """Log an event if the command is missing"""
        if command not in self.amd_smi_commands:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"amd-smi does not support command: `{command}`, it was not found in the help output",
                priority=EventPriority.INFO,
            )
            return False
        return True

    def build_amdsmi_sub_data(
        self, amd_smi_data_model: type[T], json_data: list[dict] | None
    ) -> list[T] | T | None:
        try:
            if json_data is None:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="No data returned from amd-smi sub command",
                    priority=EventPriority.ERROR,
                )
                return None
            validated_data = []
            if isinstance(json_data, list):
                for data in json_data:
                    if not isinstance(data, dict):
                        self._log_event(
                            category=EventCategory.APPLICATION,
                            description="Invalid data type for amd-smi sub data",
                            data={
                                "data_type": type(data).__name__,
                                "model_name": amd_smi_data_model.__name__,
                            },
                            priority=EventPriority.WARNING,
                        )
                        return None
                    validated_data.append(amd_smi_data_model(**data))
            elif isinstance(json_data, dict):
                return amd_smi_data_model(**json_data)
            else:
                raise ValidationError(
                    f"Invalid data type for amd-smi sub data: {type(json_data).__name__}",
                    model=amd_smi_data_model,
                )
            return validated_data
        except ValidationError as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Failed to build amd-smi model {amd_smi_data_model.__name__}",
                data=get_exception_traceback(e),
                priority=EventPriority.WARNING,
            )
            return None

    def _get_amdsmi_data(self) -> AmdSmiData | None:
        """Returns amd-smi tool data formatted as a AmdSmiData object

        Returns None if tool is not installed or if drivers are not loaded

        Returns:
            Union[AmdSmiData, None]: AmdSmiData object or None on failure
        """
        if not self._check_amdsmi_installed():
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amd-smi is not installed",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return None
        try:
            version = self._get_amdsmi_version()
            bad_pages = self.get_bad_pages()
            processes = self.get_process()
            partition = self.get_partition()
            firmware = self.get_firmware()
            topology = self.get_topology()
            amdsmi_metric = self.get_metric()
            amdsmi_static = self.get_static()
            gpu_list = self.get_gpu_list()
            xgmi_metric = self.get_xgmi_data_metric()
            if xgmi_metric is None:
                xgmi_metric = {"metric": {}, "link": {}}
            cper_data = self.get_cper_data()
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi sub commands",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return None

        gpu_list_model = self.build_amdsmi_sub_data(AmdSmiListItem, gpu_list)
        topo_data_model = self.build_amdsmi_sub_data(Topo, topology)
        bad_pages_model = self.build_amdsmi_sub_data(BadPages, bad_pages)
        partition_data_model = self.build_amdsmi_sub_data(Partition, partition)
        process_data_model = self.build_amdsmi_sub_data(Processes, processes)
        firmware_model = self.build_amdsmi_sub_data(Fw, firmware)
        amdsmi_metric_model = self.build_amdsmi_sub_data(AmdSmiMetric, amdsmi_metric)
        amdsmi_static_model = self.build_amdsmi_sub_data(AmdSmiStatic, amdsmi_static)
        xgmi_metric_model = self.build_amdsmi_sub_data(XgmiMetrics, xgmi_metric["metric"])
        xgmi_link_model = self.build_amdsmi_sub_data(XgmiLinks, xgmi_metric["link"])
        try:
            amd_smi_data = AmdSmiData(
                version=version,
                gpu_list=gpu_list_model,
                process=process_data_model,
                partition=partition_data_model,
                topology=topo_data_model,
                static=amdsmi_static_model,
                metric=amdsmi_metric_model,
                firmware=firmware_model,
                bad_pages=bad_pages_model,
                amdsmitst_data=self.get_amdsmitst_data(version),
                xgmi_link=xgmi_link_model,
                xgmi_metric=xgmi_metric_model,
                cper_data=cper_data,
            )
        except ValidationError as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiData model",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            return None

        return amd_smi_data

    def _get_amdsmi_version(self) -> AmdSmiVersion | None:
        """Get amdsmi version and data."""
        ret = self._run_amd_smi_dict("version")
        version_data = self.build_amdsmi_sub_data(AmdSmiVersion, ret)
        if version_data:
            return version_data[0]
        return None

    def _run_amd_smi_dict(
        self, cmd: str, sudo: bool = False, raise_event=True
    ) -> dict | list[dict] | None:
        """Run amd-smi command with json output.

        Args:
        ----
            cmd (str): command to run

        Returns:
        -------
            dict: dict of output
        """
        cmd += " --json"
        cmd_ret = self._run_amd_smi(cmd, sudo=sudo)
        if cmd_ret:
            try:
                return json.loads(cmd_ret)
            except json.JSONDecodeError as e:
                if raise_event:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Error parsing command: `{cmd}` json data",
                        data={"cmd": cmd, "exception": get_exception_traceback(e)},
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
                return None
        else:
            return None

    def _run_amd_smi(self, cmd: str, sudo: bool = False) -> str | None:
        """Run amd-smi command

        Args:
        ----
            cmd (str): command to run

        Returns:
        -------
            str: str of output
        """
        cmd_ret: CommandArtifact = self._run_system_command(f"{self.AMD_SMI_EXE} {cmd}", sudo=sudo)
        if cmd_ret.stderr != "" or cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi command",
                data={
                    "command": cmd,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        else:
            return cmd_ret.stdout

    def get_gpu_list(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi list"""
        LIST_CMD = "list"
        if not self._check_command_supported(LIST_CMD):
            # If the command is not supported, return None
            return None
        return self._run_amd_smi_dict(LIST_CMD)

    def get_process(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi process"""
        PROCESS_CMD = "process"
        if not self._check_command_supported(PROCESS_CMD):
            # If the command is not supported, return None
            return None
        return self._run_amd_smi_dict(PROCESS_CMD)

    def get_partition(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi process"""
        PARTITION_CMD = "partition"
        if not self._check_command_supported(PARTITION_CMD):
            # If the command is not supported, return None
            return None
        return self._run_amd_smi_dict(PARTITION_CMD)

    def get_topology(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi topology"""
        TOPO_CMD = "topology"
        if not self._check_command_supported(TOPO_CMD):
            # If the command is not supported, return None
            return None
        return self._run_amd_smi_dict(TOPO_CMD)

    def get_static(self) -> list[dict] | None:
        """Get data in dict format from cmd: amdsmi static"""
        STATIC_CMD = "static"
        if not self._check_command_supported(STATIC_CMD):
            # If the command is not supported, return None
            return None
        static_data = self._run_amd_smi_dict(f"{STATIC_CMD} -g all")
        if static_data is None:
            return None
        if "gpu_data" in static_data:
            static_data = static_data["gpu_data"]
        static_data_gpus = []
        for static in static_data:
            if "gpu" in static:
                static_data_gpus.append(static)
        return static_data_gpus

    def get_metric(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi metric"""
        METRIC_CMD = "metric"
        if not self._check_command_supported(METRIC_CMD):
            # If the command is not supported, return None
            return None
        metric_data = self._run_amd_smi_dict(f"{METRIC_CMD} -g all")
        if metric_data is None:
            return None
        if "gpu_data" in metric_data:
            metric_data = metric_data["gpu_data"]
        metric_data_gpus = []
        for metric in metric_data:
            if "gpu" in metric:
                metric_data_gpus.append(metric)
        return metric_data_gpus

    def get_firmware(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi firmware"""
        FW_CMD = "firmware"
        if not self._check_command_supported(FW_CMD):
            # If the command is not supported, return None
            return None
        return self._run_amd_smi_dict(FW_CMD)

    def get_bad_pages(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi bad-pages"""
        BAD_PAGE_CMD = "bad-pages"
        if self._check_command_supported(BAD_PAGE_CMD):
            # If the command is supported, run it
            return self._run_amd_smi_dict(BAD_PAGE_CMD)
        return None

    def get_xgmi_data_metric(self) -> dict[str, list[dict]] | None:
        """Get data as a list of dict from cmd: amdsmi xgmi"""
        XGMI_CMD = "xgmi"
        if not self._check_command_supported(XGMI_CMD):
            # If the command is not supported, return None
            return None
        xgmi_metric_data = self._run_amd_smi_dict(f"{XGMI_CMD} -m")
        if xgmi_metric_data is None:
            xgmi_metric_data = []
        elif "xgmi_metric" in xgmi_metric_data:
            xgmi_metric_data = xgmi_metric_data["xgmi_metric"]
            if len(xgmi_metric_data) == 1:
                xgmi_metric_data = xgmi_metric_data[0]
        xgmi_link_data = self._run_amd_smi_dict(f"{XGMI_CMD} -l", raise_event=False)
        if isinstance(xgmi_link_data, dict) and "link_status" in xgmi_link_data:
            xgmi_link_data = xgmi_link_data["link_status"]
        if xgmi_link_data is None:
            xgmi_link_data_str = self._run_amd_smi(f"{XGMI_CMD} -l --json")
            if xgmi_link_data_str is None:
                return {
                    "metric": xgmi_metric_data,
                    "link": [],
                }
            invalid_json_start = xgmi_link_data_str.find("]\n[")
            if invalid_json_start != -1:
                xgmi_link_data_str = xgmi_link_data_str[invalid_json_start + 2 :]
            try:
                xgmi_link_data = json.loads(xgmi_link_data_str)
            except json.JSONDecodeError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Error parsing xgmi link data",
                    data={
                        "xgmi_link_data": xgmi_link_data_str,
                        "exception": get_exception_traceback(e),
                    },
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                xgmi_metric_data = []
        return {
            "metric": xgmi_metric_data,
            "link": xgmi_link_data,
        }

    def get_cper_data(self) -> list[FileModel]:
        CPER_CMD = "ras"
        if not self._check_command_supported(CPER_CMD):
            # If the command is not supported, return an empty list
            return []
        AMD_SMI_CPER_FOLDER = "/tmp/amd_smi_cper"
        # Ensure the cper folder exists but is empty
        self._run_system_command(
            f"mkdir -p {AMD_SMI_CPER_FOLDER} && rm -f {AMD_SMI_CPER_FOLDER}/*.cper && rm -f {AMD_SMI_CPER_FOLDER}/*.json",
            sudo=False,
        )
        cper_cmd = self._run_amd_smi(f"{CPER_CMD} --cper --folder={AMD_SMI_CPER_FOLDER}", sudo=True)
        if cper_cmd is None:
            # Error was already logged in _run_amd_smi
            return []
        # search that a CPER is actually created here
        regex_cper_search = re.findall(r"(\w+\.cper)", cper_cmd)
        if not regex_cper_search:
            # Early exit if no CPER files were created
            return []
        # tar the cper folder
        self._run_system_command(
            f"tar -czf {AMD_SMI_CPER_FOLDER}.tar.gz -C {AMD_SMI_CPER_FOLDER} .",
            sudo=True,
        )
        # Load teh tar files
        cper_zip: BaseFileArtifact = self.ib_interface.read_file(
            f"{AMD_SMI_CPER_FOLDER}.tar.gz", encoding=None, strip=False
        )
        self._log_file_artifact(
            cper_zip.filename,
            cper_zip.contents,
        )
        io_bytes = io.BytesIO(cper_zip.contents)
        del cper_zip  # Free memory after reading the file
        try:
            with TarFile.open(fileobj=io_bytes, mode="r:gz") as tar_file:
                cper_data = []
                for member in tar_file.getmembers():
                    if member.isfile() and member.name.endswith(".cper"):
                        file_content = tar_file.extractfile(member)
                        if file_content is not None:
                            # Decode the content, ignoring errors to avoid issues with binary data
                            # that may not be valid UTF-8
                            file_content_bytes = file_content.read()
                        else:
                            file_content_bytes = b""
                        cper_data.append(
                            FileModel(file_contents=file_content_bytes, file_name=member.name)
                        )
            # Since we do not log the cper data in the data model create an invent informing the user if CPER created
            if cper_data:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="CPER data has been extracted from amd-smi",
                    data={
                        "cper_count": len(cper_data),
                    },
                    priority=EventPriority.INFO,
                )
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error extracting cper data",
                data={
                    "exception": get_exception_traceback(e),
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return []
        return cper_data

    def get_amdsmitst_data(self, amdsmi_version: AmdSmiVersion | None) -> AmdSmiTstData:
        """Get data in dict format from cmd: amdsmi amdsmitst"""
        MIN_FUNCTIONAL_AMDSMITST_ROCM_VERSION = PackageVersion("6.4.2")
        amdsmitst_data = AmdSmiTstData()
        if self.system_interaction_level != SystemInteractionLevel.DISRUPTIVE:
            return amdsmitst_data
        # This test is disruptive, so we only run it if the system interaction level is set to DISRUPTIVE
        if (
            amdsmi_version is None
            or amdsmi_version.rocm_version is None
            or MIN_FUNCTIONAL_AMDSMITST_ROCM_VERSION > PackageVersion(amdsmi_version.rocm_version)
        ):
            # In versions of ROCm prior to 6.4.1, the amdsmitst had a bug that would cause the sclk to get pinned
            # To a constant value, so we do not run the test for older rocm see: SWDEV-496150
            self.logger.info("Skipping amdsmitst test due to Version incompatibility")
            return amdsmitst_data
        amdsmitst_cmd: str = "/opt/rocm/share/amd_smi/tests/amdsmitst"
        cmd_ret: CommandArtifact = self._run_system_command(amdsmitst_cmd, sudo=True)
        if cmd_ret.stderr != "" or cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amdsmitst command",
                data={
                    "command": amdsmitst_cmd,
                    "exit_code": cmd_ret.exit_code,
                    "stderr": cmd_ret.stderr,
                },
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return amdsmitst_data

        passed_test_pat = r"\[\s+OK\s+\] (.*?) \(\d+ ms\)"
        skipped_test_pat = r"\[\s+SKIPPED\s+\] (.*?) \(\d+ ms\)"
        failed_test_pat = r"\[\s+FAILED\s+\] (.*?) \(\d+ ms\)"

        for ret_line in cmd_ret.stdout.splitlines():
            if match := re.match(passed_test_pat, ret_line):
                amdsmitst_data.passed_tests.append(match.group(1))
            elif match := re.match(skipped_test_pat, ret_line):
                amdsmitst_data.skipped_tests.append(match.group(1))
            elif match := re.match(failed_test_pat, ret_line):
                amdsmitst_data.failed_tests.append(match.group(1))

        amdsmitst_data.passed_test_count = len(amdsmitst_data.passed_tests)
        amdsmitst_data.skipped_test_count = len(amdsmitst_data.skipped_tests)
        amdsmitst_data.failed_test_count = len(amdsmitst_data.failed_tests)

        return amdsmitst_data

    def detect_amdsmi_commands(self) -> set[str]:
        r"""Runs the help command to determine if a amd-smi command can be used.

        Uses the regex `^\s{4}(\w+)\s` to find all commands in the help output.

        Returns:
            set[str]: _description_
        """
        command_pattern = re.compile(r"^\s{4}([\w\-]+)\s", re.MULTILINE)

        # run command with help
        help_output = self._run_amd_smi("-h")
        if help_output is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi help command",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return set()
        # Find all matches in the provided output
        commands = command_pattern.findall(help_output)
        return set(commands)

    def collect_data(
        self,
        **kwargs,
    ) -> tuple[TaskResult, AmdSmiData | None]:
        try:
            self.amd_smi_commands = self.detect_amdsmi_commands()
            amd_smi_data = self._get_amdsmi_data()
            return self.result, amd_smi_data
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi collector",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None
