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
from typing import cast

from pydantic import ValidationError

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
    FwListItem,
    Partition,
    PartitionCurrent,
    PartitionMemory,
    Processes,
    ProcessInfo,
    ProcessListItem,
    StaticAsic,
    StaticBoard,
    StaticBus,
    StaticNuma,
    StaticVbios,
    StaticVram,
    ValueUnit,
)
from nodescraper.utils import get_exception_details, get_exception_traceback


class AmdSmiCollector(InBandDataCollector[AmdSmiDataModel, None]):
    """class for collection of inband tool amd-smi data."""

    AMD_SMI_EXE = "amd-smi"

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AmdSmiDataModel

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
                description="Failed to import amdsmi package, please ensure amdsmi is installed and Python bindings are available",
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
            statics = self.get_static()
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

        try:
            return AmdSmiDataModel(
                version=version,
                gpu_list=gpu_list,
                process=processes,
                partition=partition,
                firmware=firmware,
                static=statics,
            )
        except ValidationError as e:
            self.logger.warning("Validation err: %s", e)
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiDataModel",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            return None

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

    def get_gpu_list(self) -> list[AmdSmiListItem] | None:
        devices = self._get_handles()
        out: list[AmdSmiListItem] = []

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

            try:
                out.append(
                    AmdSmiListItem(
                        gpu=idx,
                        bdf=bdf,
                        uuid=uuid,
                        kfd_id=_to_int(kfd.get("kfd_id", 0)) if isinstance(kfd, dict) else 0,
                        node_id=_to_int(kfd.get("node_id", 0)) if isinstance(kfd, dict) else 0,
                        partition_id=partition_id,
                    )
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiListItem",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_process(self) -> list[Processes] | None:
        devices = self._get_handles()
        out: list[Processes] = []
        for idx, h in enumerate(devices):
            try:
                pids = self._amdsmi.amdsmi_get_gpu_process_list(h) or []
                plist: list[ProcessListItem] = []

                for pid in pids:
                    pinfo = self._smi_try(
                        self._amdsmi.amdsmi_get_gpu_compute_process_info, h, pid, default=None
                    )
                    if not isinstance(pinfo, dict):
                        plist.append(ProcessListItem(process_info=str(pid)))
                        continue

                    plist.append(
                        ProcessListItem(
                            process_info=cast(
                                ProcessInfo,
                                {
                                    "name": pinfo.get("name", str(pid)),
                                    "pid": int(pid),
                                    "memory_usage": {
                                        "gtt_mem": ValueUnit(
                                            value=pinfo.get("gtt_mem", 0), unit="B"
                                        ),
                                        "cpu_mem": ValueUnit(
                                            value=pinfo.get("cpu_mem", 0), unit="B"
                                        ),
                                        "vram_mem": ValueUnit(
                                            value=pinfo.get("vram_mem", 0), unit="B"
                                        ),
                                    },
                                    "mem_usage": ValueUnit(
                                        value=pinfo.get("vram_mem", 0), unit="B"
                                    ),
                                    "usage": {
                                        "gfx": ValueUnit(value=pinfo.get("gfx", 0), unit="%"),
                                        "enc": ValueUnit(value=pinfo.get("enc", 0), unit="%"),
                                    },
                                },
                            )
                        )
                    )
                try:
                    out.append(Processes(gpu=idx, process_list=plist))
                except ValidationError as e:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Failed to build Processes",
                        data={"exception": get_exception_traceback(e), "gpu_index": idx},
                        priority=EventPriority.WARNING,
                    )
            except self._amdsmi.AmdSmiException as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Process collection failed",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )
        return out

    def get_partition(self) -> Partition | None:
        devices = self._get_handles()
        current: list[PartitionCurrent] = []
        memparts: list[PartitionMemory] = []
        resources: list[dict] = []  # keep as-is if your model allows

        for idx, h in enumerate(devices):
            c = self._smi_try(self._amdsmi.amdsmi_get_gpu_compute_partition, h, default={}) or {}
            m = self._smi_try(self._amdsmi.amdsmi_get_gpu_memory_partition, h, default={}) or {}
            c_dict = c if isinstance(c, dict) else {}
            m_dict = m if isinstance(m, dict) else {}

            current.append(
                PartitionCurrent(
                    gpu_id=idx,
                    memory=c_dict.get("memory"),
                    accelerator_type=c_dict.get("accelerator_type"),
                    accelerator_profile_index=c_dict.get("accelerator_profile_index"),
                    partition_id=c_dict.get("partition_id"),
                )
            )
            memparts.append(
                PartitionMemory(
                    gpu_id=idx,
                    memory_partition_caps=m_dict.get("memory_partition_caps"),
                    current_partition_id=m_dict.get("current_partition_id"),
                )
            )

        try:
            return Partition(
                current_partition=current,
                memory_partition=memparts,
                partition_resources=resources,
            )
        except ValidationError as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build Partition",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return None

    def get_firmware(self) -> list[Fw] | None:
        devices = self._get_handles()
        out: list[Fw] = []

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

            normalized: list[FwListItem] = []
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
                        FwListItem(
                            fw_id="" if fid is None else str(fid),
                            fw_version="" if ver is None else str(ver),
                        )
                    )
                elif isinstance(e, (tuple, list)) and len(e) >= 2:
                    normalized.append(FwListItem(fw_id=str(e[0]), fw_version=str(e[1])))
                else:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Unrecognized firmware entry shape",
                        data={"entry_repr": repr(e)},
                        priority=EventPriority.INFO,
                    )

            try:
                out.append(Fw(gpu=idx, fw_list=normalized))
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build Fw",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )

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

            if name in ("AMDSMI_STATUS_NOT_SUPPORTED", "AMDSMI_STATUS_NOT_FOUND"):
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn.__name__} not supported on this device/mode (status={name}, code={code})",
                    priority=EventPriority.WARNING,
                )
                return default
            if name == "AMDSMI_STATUS_PERMISSION":
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn.__name__} permission denied (need access to /dev/kfd & render nodes, or root for RAS). status={name}, code={code})",
                    priority=EventPriority.WARNING,
                )
                return default

            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{fn.__name__} failed (status={name}, code={code})",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return default

    def get_static(self) -> list[AmdSmiStatic] | None:
        devices = self._get_handles()
        if not devices:
            return []

        def _nz(val: object, default: str = "unknown") -> str:
            """Normalize possibly-empty/NA strings to a non-empty default."""
            s = str(val).strip() if val is not None else ""
            return s if s and s.upper() != "N/A" else default

        def _vu(val: object, unit: str) -> ValueUnit | None:
            """Build ValueUnit from mixed numeric/string input, else None."""
            if val in (None, "", "N/A"):
                return None
            try:
                if isinstance(val, str):
                    v = float(val) if any(ch in val for ch in ".eE") else int(val)
                elif isinstance(val, float):
                    v = val
                else:
                    v = int(val)
            except Exception:
                return None
            return ValueUnit(value=v, unit=unit)

        pcie_fn = getattr(self._amdsmi, "amdsmi_get_pcie_info", None)

        out: list[AmdSmiStatic] = []

        for idx, h in enumerate(devices):
            board = self._smi_try(self._amdsmi.amdsmi_get_gpu_board_info, h, default={}) or {}
            asic = self._smi_try(self._amdsmi.amdsmi_get_gpu_asic_info, h, default={}) or {}
            bdf = self._smi_try(self._amdsmi.amdsmi_get_gpu_device_bdf, h, default="") or ""
            _ = self._smi_try(self._amdsmi.amdsmi_get_gpu_device_uuid, h, default="")  # TODO
            kfd = self._smi_try(self._amdsmi.amdsmi_get_gpu_kfd_info, h, default={}) or {}

            # Bus / PCIe
            if callable(pcie_fn):
                p = self._smi_try(pcie_fn, h, default={}) or {}
                if isinstance(p, dict):
                    max_w = p.get("max_link_width")
                    max_s = p.get("max_link_speed")
                    pcie_ver = p.get("pcie_version") or p.get("pcie_interface_version")
                    bus = StaticBus(
                        bdf=bdf,
                        max_pcie_width=_vu(max_w, "x"),
                        max_pcie_speed=_vu(max_s, "GT/s"),
                        pcie_interface_version=_nz(pcie_ver),
                        slot_type=_nz(p.get("slot_type")),
                    )
                else:
                    bus = StaticBus(
                        bdf=bdf,
                        max_pcie_width=None,
                        max_pcie_speed=None,
                        pcie_interface_version="unknown",
                        slot_type="unknown",
                    )
            else:
                bus = StaticBus(
                    bdf=bdf,
                    max_pcie_width=None,
                    max_pcie_speed=None,
                    pcie_interface_version="unknown",
                    slot_type="unknown",
                )

            # ASIC
            asic_model = StaticAsic(
                market_name=_nz(asic.get("market_name") or asic.get("asic_name"), default=""),
                vendor_id=str(asic.get("vendor_id", "")),
                vendor_name=str(asic.get("vendor_name", "")),
                subvendor_id=str(asic.get("subvendor_id", "")),
                device_id=str(asic.get("device_id", "")),
                subsystem_id=str(asic.get("subsystem_id", "")),
                rev_id=str(asic.get("rev_id", "")),
                asic_serial=str(asic.get("asic_serial", "")),
                oam_id=int(asic.get("oam_id", 0) or 0),
                num_compute_units=int(asic.get("num_compute_units", 0) or 0),
                target_graphics_version=str(asic.get("target_graphics_version", "")),
            )

            # Board
            board_model = StaticBoard(
                model_number=str(
                    board.get("model_number", "") or board.get("amdsmi_model_number", "")
                ),
                product_serial=str(board.get("product_serial", "")),
                fru_id=str(board.get("fru_id", "")),
                product_name=str(board.get("product_name", "")),
                manufacturer_name=str(board.get("manufacturer_name", "")),
            )

            # VBIOS
            vb = {
                k: board[k]
                for k in ("vbios_name", "vbios_build_date", "vbios_part_number", "vbios_version")
                if k in board
            }
            vbios_model: StaticVbios | None = None
            if vb:
                vbios_model = StaticVbios(
                    name=str(vb.get("vbios_name", "")),
                    build_date=str(vb.get("vbios_build_date", "")),
                    part_number=str(vb.get("vbios_part_number", "")),
                    version=str(vb.get("vbios_version", "")),
                )

            # NUMA (via KFD)
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
            numa_model = StaticNuma(node=numa_node, affinity=affinity)

            # VRAM
            vram_type = str(asic.get("vram_type", "") or "unknown")
            vram_vendor = asic.get("vram_vendor")
            vram_bits = asic.get("vram_bit_width")
            vram_size_b: int | None = None
            if asic.get("vram_size_bytes") is not None:
                try:
                    vram_size_b = int(asic["vram_size_bytes"])
                except Exception:
                    vram_size_b = None
            elif asic.get("vram_size_mb") is not None:
                try:
                    vram_size_b = int(asic["vram_size_mb"]) * 1024 * 1024
                except Exception:
                    vram_size_b = None

            vram_model = StaticVram(
                type=vram_type,
                vendor=None if vram_vendor in (None, "", "N/A") else str(vram_vendor),
                size=_vu(vram_size_b, "B"),
                bit_width=_vu(vram_bits, "bit"),
                max_bandwidth=None,
            )

            try:
                out.append(
                    AmdSmiStatic(
                        gpu=idx,
                        asic=asic_model,
                        bus=bus,
                        vbios=vbios_model,
                        limit=None,  # not available via API
                        board=board_model,
                        soc_pstate=None,  # TODO
                        xgmi_plpd=None,  # TODO
                        process_isolation="",
                        numa=numa_model,
                        vram=vram_model,
                        cache_info=[],  # TODO
                        partition=None,
                        clock=None,  # TODO
                    )
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiStatic",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
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
