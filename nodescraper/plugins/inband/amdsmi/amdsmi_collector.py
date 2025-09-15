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
from typing import TypeVar

from pydantic import BaseModel, ValidationError

try:
    import amdsmi  # noqa: F401
    from amdsmi import (
        AmdSmiException,
        AmdSmiInitFlags,
        amdsmi_get_fw_info,
        amdsmi_get_gpu_compute_partition,
        amdsmi_get_gpu_compute_process_info,
        amdsmi_get_gpu_device_bdf,
        amdsmi_get_gpu_device_uuid,
        amdsmi_get_gpu_kfd_info,
        amdsmi_get_gpu_memory_partition,
        amdsmi_get_gpu_process_list,
        amdsmi_get_lib_version,
        amdsmi_get_processor_handles,
        amdsmi_get_rocm_version,
        amdsmi_init,
        amdsmi_shut_down,
    )

    _AMDSMI_IMPORT_ERROR = None
except Exception as _e:
    _AMDSMI_IMPORT_ERROR = _e

from nodescraper.base.inbandcollectortask import InBandDataCollector
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiListItem,
    AmdSmiVersion,
    Fw,
    Partition,
    Processes,
)
from nodescraper.utils import get_exception_details, get_exception_traceback

T = TypeVar("T", bound=BaseModel)


class AmdSmiCollector(InBandDataCollector[AmdSmiDataModel, None]):
    """class for collection of inband tool amd-smi data."""

    AMD_SMI_EXE = "amd-smi"

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AmdSmiDataModel

    def _get_handles(self):
        """Get processor handles."""
        try:
            return amdsmi_get_processor_handles()
        except amdsmi.AmdSmiException as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_processor_handles failed",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return []

    def build_amdsmi_sub_data(
        self, amd_smi_data_model: type[T], json_data: list[dict] | dict | None
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

    def _get_amdsmi_data(self) -> AmdSmiDataModel | None:
        """Returns amd-smi tool data formatted as a AmdSmiDataModel object

        Returns None if tool is not installed or if drivers are not loaded

        Returns:
            Union[AmdSmiDataModel, None]: AmdSmiDataModel object or None on failure
        """
        try:
            version = self._get_amdsmi_version()
            processes = self.get_process()
            partition = self.get_partition()
            firmware = self.get_firmware()
            gpu_list = self.get_gpu_list()
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

        partition_data_model = self.build_amdsmi_sub_data(Partition, partition)
        process_data_model = self.build_amdsmi_sub_data(Processes, processes)
        firmware_model = self.build_amdsmi_sub_data(Fw, firmware)
        gpu_list_model = self.build_amdsmi_sub_data(AmdSmiListItem, gpu_list)
        try:
            amd_smi_data = AmdSmiDataModel(
                version=version,
                gpu_list=gpu_list_model,
                process=process_data_model,
                partition=partition_data_model,
                firmware=firmware_model,
            )
        except ValidationError as e:
            self.logger.warning("Validation err: %s", e)
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiDataModel model",
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

        def _to_int(x, default=0):
            try:
                return int(x)
            except Exception:
                return default

        for idx, h in enumerate(devices):
            bdf = self._smi_try(amdsmi_get_gpu_device_bdf, h, default="") or ""
            uuid = self._smi_try(amdsmi_get_gpu_device_uuid, h, default="") or ""
            kfd = self._smi_try(amdsmi_get_gpu_kfd_info, h, default={}) or {}

            partition_id = 0
            cp = self._smi_try(amdsmi_get_gpu_compute_partition, h, default={}) or {}
            if isinstance(cp, dict) and cp.get("partition_id") is not None:
                partition_id = _to_int(cp.get("partition_id"), 0)
            else:
                mp = self._smi_try(amdsmi_get_gpu_memory_partition, h, default={}) or {}
                if isinstance(mp, dict) and mp.get("current_partition_id") is not None:
                    partition_id = _to_int(mp.get("current_partition_id"), 0)

            out.append(
                {
                    "gpu": idx,
                    "bdf": bdf,
                    "uuid": uuid,
                    "kfd_id": _to_int(kfd.get("kfd_id", 0)) if isinstance(kfd, dict) else 0,
                    "node_id": _to_int(kfd.get("node_id", 0)) if isinstance(kfd, dict) else 0,
                    "partition_id": partition_id,
                }
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
                    pinfo = self._smi_try(amdsmi_get_gpu_compute_process_info, h, pid, default=None)
                    if not isinstance(pinfo, dict):
                        plist.append({"process_info": str(pid)})
                        continue

                    plist.append(
                        {
                            "process_info": {
                                "name": pinfo.get("name", str(pid)),
                                "pid": int(pid),
                                "memory_usage": {
                                    "gtt_mem": {"value": pinfo.get("gtt_mem", 0), "unit": "B"},
                                    "cpu_mem": {"value": pinfo.get("cpu_mem", 0), "unit": "B"},
                                    "vram_mem": {"value": pinfo.get("vram_mem", 0), "unit": "B"},
                                },
                                "mem_usage": {"value": pinfo.get("vram_mem", 0), "unit": "B"},
                                "usage": {
                                    "gfx": {"value": pinfo.get("gfx", 0), "unit": "%"},
                                    "enc": {"value": pinfo.get("enc", 0), "unit": "%"},
                                },
                            }
                        }
                    )
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
        resources: list[dict] = []
        for idx, h in enumerate(devices):
            c = self._smi_try(amdsmi_get_gpu_compute_partition, h, default={}) or {}
            m = self._smi_try(amdsmi_get_gpu_memory_partition, h, default={}) or {}
            c_dict = c if isinstance(c, dict) else {}
            m_dict = m if isinstance(m, dict) else {}
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
            "partition_resources": resources,
        }

    def get_firmware(self) -> list[dict] | None:
        devices = self._get_handles()
        out: list[dict] = []

        for idx, h in enumerate(devices):
            raw = self._smi_try(amdsmi_get_fw_info, h, default=None)
            if raw is None:
                continue

            if isinstance(raw, list):
                items = raw
            elif isinstance(raw, dict):
                if isinstance(raw.get("fw_list"), list):
                    items = raw["fw_list"]
                elif raw and all(not isinstance(v, (dict, list, tuple)) for v in raw.values()):
                    items = [{"fw_id": k, "fw_version": v} for k, v in raw.items()]
                else:
                    items = [raw]
            else:
                items = []

            normalized: list[dict] = []
            for e in items:
                if isinstance(e, dict):
                    fid = (
                        e.get("fw_id")
                        or e.get("fw_name")
                        or e.get("name")
                        or e.get("block")
                        or e.get("type")
                        or e.get("id")
                    )
                    ver = e.get("fw_version") or e.get("version") or e.get("fw_ver") or e.get("ver")
                    normalized.append(
                        {
                            "fw_id": "" if fid is None else str(fid),
                            "fw_version": "" if ver is None else str(ver),
                        }
                    )
                elif isinstance(e, (tuple, list)) and len(e) >= 2:
                    normalized.append({"fw_id": str(e[0]), "fw_version": str(e[1])})
                else:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Unrecognized firmware entry shape",
                        data={"entry_repr": repr(e)},
                        priority=EventPriority.INFO,
                    )

            out.append({"gpu": idx, "fw_list": normalized})

        return out

    def _smi_try(self, fn, *a, default=None, **kw):
        """Call an AMDSMI function and normalize common library errors.
        Extracts numeric ret_code from exceptions that don't expose a .status enum.
        """
        try:
            return fn(*a, **kw)
        except AmdSmiException as e:
            self.logger.warning(e)
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
    ) -> tuple[TaskResult, AmdSmiDataModel | None]:

        if _AMDSMI_IMPORT_ERROR is not None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to import amdsmi Python bindings",
                data={"exception": get_exception_traceback(_AMDSMI_IMPORT_ERROR)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        try:
            amdsmi_init(AmdSmiInitFlags.INIT_AMD_GPUS)
            amd_smi_data = self._get_amdsmi_data()  # fails ras not found

            if amd_smi_data is None:
                return self.result, None

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
        finally:
            try:
                amdsmi_shut_down()
            except Exception:
                pass
