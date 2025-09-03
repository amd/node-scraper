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
from tarfile import TarFile
from typing import TypeVar

import amdsmi
from amdsmi import (
    AmdSmiException,
    AmdSmiInitFlags,
    amdsmi_get_fw_info,
    amdsmi_get_gpu_accelerator_partition_profile,
    amdsmi_get_gpu_asic_info,
    amdsmi_get_gpu_bad_page_info,
    amdsmi_get_gpu_board_info,
    amdsmi_get_gpu_compute_partition,
    amdsmi_get_gpu_compute_process_info,
    amdsmi_get_gpu_device_bdf,
    amdsmi_get_gpu_device_uuid,
    amdsmi_get_gpu_kfd_info,
    amdsmi_get_gpu_memory_partition,
    amdsmi_get_gpu_memory_reserved_pages,
    amdsmi_get_gpu_process_list,
    amdsmi_get_lib_version,
    amdsmi_get_processor_handles,
    amdsmi_get_rocm_version,
    amdsmi_init,
    amdsmi_shut_down,
)
from packaging.version import Version as PackageVersion
from pydantic import BaseModel, ValidationError

from nodescraper.base.inbandcollectortask import InBandDataCollector

# from nodescraper.models.datamodel import FileModel
from nodescraper.connection.inband import BinaryFileArtifact, TextFileArtifact
from nodescraper.connection.inband.inband import BaseFileArtifact, CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models import TaskResult
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

    def _get_handles(self):
        """Get processor handles."""
        try:
            return amdsmi_get_processor_handles()
        except amdsmi.AmdSmiException as e:
            print("Exception1: %s" % e)
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_processor_handles failed",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return []

    def _check_amdsmi_installed(self) -> bool:
        """Return if amd-smi is installed"""

        cmd_ret: CommandArtifact = self._run_sut_cmd("which amd-smi")
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
        self, amd_smi_data_model: type[T], json_data: list[dict] | dict | None
    ) -> list[T] | T | None:
        try:
            if json_data is None:
                print("JSON is none")
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
            self.amd_smi_commands = self.detect_amdsmi_commands()
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
            print(e)
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
        """Get lib/rocm versions."""
        try:
            lib_ver = amdsmi_get_lib_version() or ""
            rocm_ver = amdsmi_get_rocm_version() or ""
        except AmdSmiException as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to read AMD SMI versions",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return None

        return AmdSmiVersion(
            tool="amdsmi",
            version=lib_ver,
            amdsmi_library_version=lib_ver,
            rocm_version=rocm_ver,
        )

    def _run_amd_smi_dict(
        self, cmd: str, sudo: bool = False, raise_event=True
    ) -> dict | list[dict] | None:
        """Run amd-smi command with json output."""
        cmd += " --json"
        cmd_ret = self._run_amd_smi(cmd, sudo=True if sudo else False)
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
        """Run amd-smi command"""
        cmd_ret: CommandArtifact = self._run_sut_cmd(f"{self.AMD_SMI_EXE} {cmd}", sudo=sudo)

        if cmd_ret.exit_code != 0:
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

        return cmd_ret.stdout or ""

    def get_gpu_list(self) -> list[dict] | None:
        devices = self._get_handles()
        out: list[dict] = []
        for idx, h in enumerate(devices):
            try:
                uuid = amdsmi_get_gpu_device_uuid(h) or ""
                bdf = amdsmi_get_gpu_device_bdf(h) or ""
                kfd = amdsmi_get_gpu_kfd_info(h) or {}

                # Name via board/ASIC info
                name = None
                try:
                    board = amdsmi_get_gpu_board_info(h) or {}
                    name = board.get("product_name")  # preferred
                except amdsmi.AmdSmiException:
                    pass
                if not name:
                    try:
                        asic = amdsmi_get_gpu_asic_info(h) or {}
                        name = asic.get("market_name")  # fallback
                    except amdsmi.AmdSmiException:
                        pass

                out.append(
                    {
                        "gpu": idx,
                        "name": name or "unknown",
                        "bdf": bdf,
                        "uuid": uuid,
                        "kfd_id": int(kfd.get("kfd_id", 0)) if isinstance(kfd, dict) else 0,
                        "node_id": int(kfd.get("node_id", 0)) if isinstance(kfd, dict) else 0,
                        "partition_id": 0,
                    }
                )
            except AmdSmiException as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build gpu list entry from API",
                    data={"exception": get_exception_traceback(e)},
                    priority=EventPriority.WARNING,
                )
        return out

    def get_process(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi process"""
        devices = self._get_handles()
        out: list[dict] = []
        for idx, h in enumerate(devices):
            try:
                pids = amdsmi_get_gpu_process_list(h) or []
                plist = []
                for pid in pids:
                    try:
                        pinfo = amdsmi_get_gpu_compute_process_info(h, pid) or {}
                        plist.append(
                            {
                                "process_info": {
                                    "name": pinfo.get("name", str(pid)),
                                    "pid": int(pid),
                                    "memory_usage": {
                                        "gtt_mem": {"value": pinfo.get("gtt_mem", 0), "unit": "B"},
                                        "cpu_mem": {"value": pinfo.get("cpu_mem", 0), "unit": "B"},
                                        "vram_mem": {
                                            "value": pinfo.get("vram_mem", 0),
                                            "unit": "B",
                                        },
                                    },
                                    "mem_usage": {"value": pinfo.get("vram_mem", 0), "unit": "B"},
                                    "usage": {
                                        "gfx": {"value": pinfo.get("gfx", 0), "unit": "%"},
                                        "enc": {"value": pinfo.get("enc", 0), "unit": "%"},
                                    },
                                }
                            }
                        )
                    except AmdSmiException:
                        plist.append({"process_info": str(pid)})
                out.append({"gpu": idx, "process_list": plist})
            except AmdSmiException as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Process collection failed",
                    data={"exception": get_exception_traceback(e)},
                    priority=EventPriority.WARNING,
                )
        return out

    def get_partition(self) -> dict | None:
        """Collect partition info via AMDSMI; degrade gracefully if unsupported."""
        devices = self._get_handles()
        current: list[dict] = []
        memparts: list[dict] = []
        profiles: list[dict] = []
        resources: list[dict] = []
        for idx, h in enumerate(devices):
            c = self._smi_try(amdsmi_get_gpu_compute_partition, h, default={}) or {}
            m = self._smi_try(amdsmi_get_gpu_memory_partition, h, default={}) or {}
            p = self._smi_try(amdsmi_get_gpu_accelerator_partition_profile, h, default={}) or {}
            c_dict = c if isinstance(c, dict) else {}
            m_dict = m if isinstance(m, dict) else {}
            profiles.append(p if isinstance(p, dict) else {})
            current.append(
                {
                    "gpu_id": idx,
                    "memory": c_dict.get("memory"),
                    "accelerator_type": c_dict.get("accelerator_type"),
                    "accelerator_profile_index": c_dict.get("accelerator_profile_index"),
                    "partition_id": c_dict.get("partition_id"),
                }
            )
            memparts.append(
                {
                    "gpu_id": idx,
                    "memory_partition_caps": m_dict.get("memory_partition_caps"),
                    "current_partition_id": m_dict.get("current_partition_id"),
                }
            )
        return {
            "current_partition": current,
            "memory_partition": memparts,
            "partition_profiles": profiles,
            "partition_resources": resources,
        }

    def get_topology(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi topology"""
        TOPO_CMD = "topology"
        if not hasattr(self, "amd_smi_commands"):
            self.amd_smi_commands = self.detect_amdsmi_commands()
        if not self._check_command_supported(TOPO_CMD):
            return None
        return self._run_amd_smi_dict(TOPO_CMD)

    def get_static(self) -> list[dict] | None:
        """Get data in dict format from cmd: amdsmi static"""
        STATIC_CMD = "static"
        if not hasattr(self, "amd_smi_commands"):
            self.amd_smi_commands = self.detect_amdsmi_commands()
        if not self._check_command_supported(STATIC_CMD):
            return None
        static_data = self._run_amd_smi_dict(f"{STATIC_CMD} -g all")
        if static_data is None:
            return None
        if isinstance(static_data, dict) and "gpu_data" in static_data:
            static_data = static_data["gpu_data"]
        static_data_gpus = []
        for static in static_data:
            if isinstance(static, dict) and "gpu" in static:
                static_data_gpus.append(static)
        return static_data_gpus

    def get_metric(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi metric"""
        METRIC_CMD = "metric"
        if not hasattr(self, "amd_smi_commands"):
            self.amd_smi_commands = self.detect_amdsmi_commands()
        if not self._check_command_supported(METRIC_CMD):
            return None
        metric_data = self._run_amd_smi_dict(f"{METRIC_CMD} -g all")
        if metric_data is None:
            return None
        if isinstance(metric_data, dict) and "gpu_data" in metric_data:
            metric_data = metric_data["gpu_data"]
        metric_data_gpus = []
        for metric in metric_data:
            if isinstance(metric, dict) and "gpu" in metric:
                metric_data_gpus.append(metric)
        return metric_data_gpus

    def get_firmware(self) -> list[dict] | None:
        """Get data as a list of dict from cmd: amdsmi firmware"""
        devices = self._get_handles()
        out: list[dict] = []
        for idx, h in enumerate(devices):
            try:
                fw_list = amdsmi_get_fw_info(h) or []
                out.append(
                    {
                        "gpu": idx,
                        "fw_list": [
                            {"fw_id": f.get("fw_id", ""), "fw_version": f.get("fw_version", "")}
                            for f in fw_list
                            if isinstance(f, dict)
                        ],
                    }
                )
            except AmdSmiException as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="amdsmi_get_fw_info failed",
                    data={"exception": get_exception_traceback(e)},
                    priority=EventPriority.WARNING,
                )
        return out

    def get_bad_pages(self) -> list[dict] | None:
        devices = self._get_handles()
        print("devices: %s" % (devices,))
        out: list[dict] = []
        for idx, h in enumerate(devices):
            bad_list = self._smi_try(amdsmi_get_gpu_bad_page_info, h, default=[]) or []
            res_list = self._smi_try(amdsmi_get_gpu_memory_reserved_pages, h, default=[]) or []

            retired = sum(
                1
                for b in bad_list
                if isinstance(b, dict) and str(b.get("status", "")).lower() == "retired"
            )
            pending = sum(
                1
                for b in bad_list
                if isinstance(b, dict) and str(b.get("status", "")).lower() == "pending"
            )

            out.append(
                {
                    "gpu": idx,
                    "retired": retired,
                    "pending": pending,
                    "un_res": len(res_list),
                    "bad_pages": bad_list,
                    "reserved_pages": res_list,
                }
            )
        return out

    def get_xgmi_data_metric(self) -> dict[str, list[dict]] | None:
        """Get data as a list of dict from cmd: amdsmi xgmi"""
        XGMI_CMD = "xgmi"
        if not hasattr(self, "amd_smi_commands"):
            self.amd_smi_commands = self.detect_amdsmi_commands()
        if not self._check_command_supported(XGMI_CMD):
            return None
        xgmi_metric_data = self._run_amd_smi_dict(f"{XGMI_CMD} -m")
        if xgmi_metric_data is None:
            xgmi_metric_data = []
        elif isinstance(xgmi_metric_data, dict) and "xgmi_metric" in xgmi_metric_data:
            xgmi_metric_data = xgmi_metric_data["xgmi_metric"]
            if isinstance(xgmi_metric_data, list) and len(xgmi_metric_data) == 1:
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

    def get_cper_data(self) -> list[TextFileArtifact]:
        CPER_CMD = "ras"
        if not hasattr(self, "amd_smi_commands"):
            self.amd_smi_commands = self.detect_amdsmi_commands()
        if not self._check_command_supported(CPER_CMD):
            return []
        AMD_SMI_CPER_FOLDER = "/tmp/amd_smi_cper"
        self._run_sut_cmd(
            f"mkdir -p {AMD_SMI_CPER_FOLDER} && rm -f {AMD_SMI_CPER_FOLDER}/*.cper && rm -f {AMD_SMI_CPER_FOLDER}/*.json",
            sudo=False,
        )
        cper_cmd = self._run_amd_smi(f"{CPER_CMD} --cper --folder={AMD_SMI_CPER_FOLDER}", sudo=True)
        if cper_cmd is None:
            return []
        regex_cper_search = re.findall(r"(\w+\.cper)", cper_cmd)
        if not regex_cper_search:
            return []
        self._run_sut_cmd(
            f"tar -czf {AMD_SMI_CPER_FOLDER}.tar.gz -C {AMD_SMI_CPER_FOLDER} .",
            sudo=True,
        )
        cper_zip: BaseFileArtifact = self.ib_interface.read_file(
            f"{AMD_SMI_CPER_FOLDER}.tar.gz", encoding=None, strip=False
        )
        self._log_file_artifact(
            cper_zip.filename,
            cper_zip.contents,
        )
        io_bytes = io.BytesIO(cper_zip.contents)
        del cper_zip
        try:
            with TarFile.open(fileobj=io_bytes, mode="r:gz") as tar_file:
                cper_data = []
                for member in tar_file.getmembers():
                    if member.isfile() and member.name.endswith(".cper"):
                        file_content = tar_file.extractfile(member)
                        if file_content is not None:
                            file_content_bytes = file_content.read()
                        else:
                            file_content_bytes = b""
                        cper_data.append(
                            BinaryFileArtifact(filename=member.name, contents=file_content_bytes)
                        )
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
        if (
            amdsmi_version is None
            or amdsmi_version.rocm_version is None
            or MIN_FUNCTIONAL_AMDSMITST_ROCM_VERSION > PackageVersion(amdsmi_version.rocm_version)
        ):
            self.logger.info("Skipping amdsmitst test due to Version incompatibility")
            return amdsmitst_data
        amdsmitst_cmd: str = "/opt/rocm/share/amd_smi/tests/amdsmitst"
        cmd_ret: CommandArtifact = self._run_sut_cmd(amdsmitst_cmd, sudo=True)
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
            m = re.match(passed_test_pat, ret_line)
            if m:
                amdsmitst_data.passed_tests.append(m.group(1))
                continue
            m = re.match(skipped_test_pat, ret_line)
            if m:
                amdsmitst_data.skipped_tests.append(m.group(1))
                continue
            m = re.match(failed_test_pat, ret_line)
            if m:
                amdsmitst_data.failed_tests.append(m.group(1))

        amdsmitst_data.passed_test_count = len(amdsmitst_data.passed_tests)
        amdsmitst_data.skipped_test_count = len(amdsmitst_data.skipped_tests)
        amdsmitst_data.failed_test_count = len(amdsmitst_data.failed_tests)

        return amdsmitst_data

    def detect_amdsmi_commands(self) -> set[str]:
        r"""Runs the help command to determine if a amd-smi command can be used."""
        command_pattern = re.compile(r"^\s{4}([\w\-]+)\s", re.MULTILINE)
        help_output = self._run_amd_smi("-h")
        if help_output is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi help command",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return set()
        commands = command_pattern.findall(help_output)
        return set(commands)

    def _smi_try(self, fn, *a, default=None, **kw):
        """Call an AMDSMI function and normalize common library errors.
        Extracts numeric ret_code from exceptions that don't expose a .status enum.
        """
        try:
            return fn(*a, **kw)
        except AmdSmiException as e:
            code = getattr(e, "ret_code", None)
            if code is None:
                try:
                    code = int(e.args[0]) if getattr(e, "args", None) else None
                except Exception:
                    code = None
            CODE2NAME = {
                1: "AMDSMI_STATUS_SUCCESS",
                2: "AMDSMI_STATUS_NOT_SUPPORTED",
                3: "AMDSMI_STATUS_PERMISSION",
                4: "AMDSMI_STATUS_OUT_OF_RESOURCES",
                5: "AMDSMI_STATUS_INIT_ERROR",
                6: "AMDSMI_STATUS_INPUT_OUT_OF_BOUNDS",
                7: "AMDSMI_STATUS_NOT_FOUND",
            }
            name = CODE2NAME.get(code, "unknown")

            if name == "AMDSMI_STATUS_NOT_SUPPORTED" or name == "AMDSMI_STATUS_NOT_FOUND":
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn.__name__} not supported on this device/mode (status={name}, code={code})",
                    priority=EventPriority.WARNING,
                )
                return default
            if name == "AMDSMI_STATUS_PERMISSION":
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn.__name__} permission denied (need access to /dev/kfd & render nodes, or root for RAS). status={name}, code={code}",
                    priority=EventPriority.WARNING,
                )
                return default
            # Generic case
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{fn.__name__} failed (status={name}, code={code})",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return default
            if name == "AMDSMI_STATUS_PERMISSION":
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn.__name__} permission denied (need access to /dev/kfd and render nodes). status={name}, code={code}",
                    priority=EventPriority.WARNING,
                )
                return default
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{fn.__name__} failed (status={name or 'unknown'}, code={code})",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return default
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{fn.__name__} failed",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return default

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, AmdSmiData | None]:
        try:
            amdsmi_init(AmdSmiInitFlags.INIT_AMD_GPUS)

            for h in self._get_handles():
                board = self._smi_try(amdsmi_get_gpu_board_info, h, default={}) or {}
                asic = self._smi_try(amdsmi_get_gpu_asic_info, h, default={}) or {}
                name = board.get("product_name") or asic.get("market_name")
                uuid = self._smi_try(amdsmi_get_gpu_device_uuid, h, default=None)
                kfd = self._smi_try(amdsmi_get_gpu_kfd_info, h, default={}) or {}
                print({"name": name, "uuid": uuid, "kfd": kfd})

            amd_smi_data = None
            version = self._get_amdsmi_version()
            bad_pages = self.get_bad_pages()  # call fails, need ras?
            processes = self.get_process()
            partition = self.get_partition()  # call fails
            firmware = self.get_firmware()
            topology = self.get_topology()
            amdsmi_metric = self.get_metric()
            amdsmi_static = self.get_static()
            gpu_list = self.get_gpu_list()
            xgmi_metric = self.get_xgmi_data_metric()
            if xgmi_metric is None:
                xgmi_metric = {"metric": {}, "link": {}}
            cper_data = self.get_cper_data()
            amd_smi_data = self._get_amdsmi_data()  # fails ras not found
            if amd_smi_data is None:
                return self.result, None

            amd_smi_data = self._get_amdsmi_data()
            if amd_smi_data is None:
                return self.result, None

            return self.result, amd_smi_data
        except Exception as e:
            print(e)
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi collector",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None
        finally:
            try:
                amdsmi_shut_down()
            except Exception:
                pass
