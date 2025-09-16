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
import importlib
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from nodescraper.base.inbandcollectortask import InBandDataCollector
from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiListItem,
    AmdSmiStatic,
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

    def _amdsmi_is_bound(self) -> bool:
        return all(name in globals() for name in ("amdsmi_init", "AmdSmiInitFlags"))

    def _bind_amdsmi_or_log(self) -> bool:
        """Import amdsmi and store the module on self. Return True if ok."""
        if getattr(self, "_amdsmi", None) is not None:
            return True
        try:
            self._amdsmi = importlib.import_module("amdsmi")
            return True
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to import amdsmi Python bindings",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return False

    def _get_handles(self):
        try:
            return self._amdsmi.amdsmi_get_processor_handles()
        except self._amdsmi.AmdSmiException as e:
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
            amdsmi_static = self.get_static()
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
        amdsmi_static_model = self.build_amdsmi_sub_data(AmdSmiStatic, amdsmi_static)
        try:
            amd_smi_data = AmdSmiDataModel(
                version=version,
                gpu_list=gpu_list_model,
                process=process_data_model,
                partition=partition_data_model,
                firmware=firmware_model,
                static=amdsmi_static_model,
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
            lib_ver = self._amdsmi.amdsmi_get_lib_version() or ""
            rocm_ver = self._amdsmi.amdsmi_get_rocm_version() or ""
        except self._amdsmi.AmdSmiException as e:
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
            bdf = self._smi_try(self._amdsmi.amdsmi_get_gpu_device_bdf, h, default="") or ""
            uuid = self._smi_try(self._amdsmi.amdsmi_get_gpu_device_uuid, h, default="") or ""
            kfd = self._smi_try(self._amdsmi.amdsmi_get_gpu_kfd_info, h, default={}) or {}

            partition_id = 0
            cp = self._smi_try(self._amdsmi.amdsmi_get_gpu_compute_partition, h, default={}) or {}
            if isinstance(cp, dict) and cp.get("partition_id") is not None:
                partition_id = _to_int(cp.get("partition_id"), 0)
            else:
                mp = (
                    self._smi_try(self._amdsmi.amdsmi_get_gpu_memory_partition, h, default={}) or {}
                )
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
                pids = self._amdsmi.amdsmi_get_gpu_process_list(h) or []
                plist = []
                for pid in pids:
                    pinfo = self._smi_try(
                        self._amdsmi.amdsmi_get_gpu_compute_process_info, h, pid, default=None
                    )
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
            c = self._smi_try(self._amdsmi.amdsmi_get_gpu_compute_partition, h, default={}) or {}
            m = self._smi_try(self._amdsmi.amdsmi_get_gpu_memory_partition, h, default={}) or {}
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
            raw = self._smi_try(self._amdsmi.amdsmi_get_fw_info, h, default=None)
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
        except self._amdsmi.AmdSmiException as e:
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

    def get_static(self) -> list[dict] | None:
        devices = self._get_handles()
        if not devices:
            return []

        _pcie_fn = globals().get("amdsmi_get_pcie_info", None)

        out: list[dict] = []

        for idx, h in enumerate(devices):
            board = self._smi_try(self._amdsmi.amdsmi_get_gpu_board_info, h, default={}) or {}
            asic = self._smi_try(self._amdsmi.amdsmi_get_gpu_asic_info, h, default={}) or {}
            bdf = self._smi_try(self._amdsmi.amdsmi_get_gpu_device_bdf, h, default="") or ""
            _ = self._smi_try(
                self._amdsmi.amdsmi_get_gpu_device_uuid, h, default=""
            )  # uuid not used here
            kfd = self._smi_try(self._amdsmi.amdsmi_get_gpu_kfd_info, h, default={}) or {}

            cache_info: list[dict] = []
            part = None
            soc_pstate = None
            xgmi_plpd = None
            clock = None
            process_isolation = ""

            # -----------------------
            # Bus / PCIe
            # -----------------------
            pcie = {}
            if callable(_pcie_fn):
                p = self._smi_try(_pcie_fn, h, default={}) or {}
                if isinstance(p, dict):
                    max_w = p.get("max_link_width")
                    max_s = p.get("max_link_speed")
                    pcie_ver = p.get("pcie_version") or p.get("pcie_interface_version")
                    pcie = {
                        "bdf": bdf,
                        "max_pcie_width": (
                            f"{max_w} x" if max_w not in (None, "", "N/A") else None
                        ),
                        "max_pcie_speed": (
                            f"{max_s} GT/s" if max_s not in (None, "", "N/A") else None
                        ),
                        "pcie_interface_version": str(pcie_ver or ""),
                        "slot_type": str(p.get("slot_type", "")),
                    }
            if not pcie:
                pcie = {
                    "bdf": bdf,
                    "max_pcie_width": None,
                    "max_pcie_speed": None,
                    "pcie_interface_version": "",
                    "slot_type": "",
                }

            # -----------------------
            # ASIC
            # -----------------------
            asic_mapped = {
                "market_name": str(asic.get("market_name") or asic.get("asic_name") or ""),
                "vendor_id": str(asic.get("vendor_id", "")),
                "vendor_name": str(asic.get("vendor_name", "")),
                "subvendor_id": str(asic.get("subvendor_id", "")),
                "device_id": str(asic.get("device_id", "")),
                "subsystem_id": str(asic.get("subsystem_id", "")),
                "rev_id": str(asic.get("rev_id", "")),
                "asic_serial": str(asic.get("asic_serial", "")),
                "oam_id": int(asic.get("oam_id", 0) or 0),
                "num_compute_units": int(asic.get("num_compute_units", 0) or 0),
                "target_graphics_version": str(asic.get("target_graphics_version", "")),
            }

            # -----------------------
            # Board
            # -----------------------
            board_mapped = {
                "model_number": str(
                    board.get("model_number", "") or board.get("amdsmi_model_number", "")
                ),
                "product_serial": str(board.get("product_serial", "")),
                "fru_id": str(board.get("fru_id", "")),
                "product_name": str(board.get("product_name", "")),
                "manufacturer_name": str(board.get("manufacturer_name", "")),
            }

            # -----------------------
            # VBIOS
            # -----------------------
            vbios = None
            vb = {}
            for k in ("vbios_name", "vbios_build_date", "vbios_part_number", "vbios_version"):
                if k in board:
                    vb[k] = board[k]
            if vb:
                vbios = {
                    "name": str(vb.get("vbios_name", "")),
                    "build_date": str(vb.get("vbios_build_date", "")),
                    "part_number": str(vb.get("vbios_part_number", "")),
                    "version": str(vb.get("vbios_version", "")),
                }

            # -----------------------
            # NUMA (from KFD)
            # -----------------------
            if isinstance(kfd, dict):
                try:
                    numa_node = int(kfd.get("node_id", 0) or 0)
                except Exception:
                    numa_node = 0
                try:
                    affinity = int(kfd.get("cpu_affinity", 0) or 0)
                except Exception:
                    affinity = 0
            else:
                numa_node, affinity = 0, 0
            numa = {"node": numa_node, "affinity": affinity}

            # -----------------------
            # VRAM
            # -----------------------
            vram_type = str(asic.get("vram_type", "") or "unknown")
            vram_vendor = asic.get("vram_vendor")
            vram_bits = asic.get("vram_bit_width")
            vram_size_b = None
            if asic.get("vram_size_bytes") is not None:
                vram_size_b = int(asic["vram_size_bytes"])
            elif asic.get("vram_size_mb") is not None:
                try:
                    vram_size_b = int(asic["vram_size_mb"]) * 1024 * 1024
                except Exception:
                    vram_size_b = None

            vram = {
                "type": vram_type,
                "vendor": None if vram_vendor in (None, "", "N/A") else str(vram_vendor),
                "size": (f"{vram_size_b} B" if isinstance(vram_size_b, int) else None),
                "bit_width": (f"{vram_bits} bit" if isinstance(vram_bits, (int, float)) else None),
                "max_bandwidth": None,
            }

            out.append(
                {
                    "gpu": idx,
                    "asic": asic_mapped,
                    "bus": pcie,
                    "vbios": vbios,
                    "limit": None,  # not available via API
                    "driver": None,
                    "board": board_mapped,
                    "ras": None,
                    "soc_pstate": soc_pstate,
                    "xgmi_plpd": xgmi_plpd,
                    "process_isolation": process_isolation,
                    "numa": numa,
                    "vram": vram,
                    "cache_info": cache_info,
                    "partition": part,
                    "clock": clock,
                }
            )

        return out

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, AmdSmiDataModel | None]:

        if not self._bind_amdsmi_or_log():
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        try:
            self._amdsmi.amdsmi_init(self._amdsmi.AmdSmiInitFlags.INIT_AMD_GPUS)
            amd_smi_data = self._get_amdsmi_data()

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
                self._amdsmi.amdsmi_shut_down()
            except Exception:
                pass
