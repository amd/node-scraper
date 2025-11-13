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
from typing import Any, Callable, Optional, Union, cast

from pydantic import ValidationError

from nodescraper.base.inbandcollectortask import InBandDataCollector
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
    PartitionCompute,
    PartitionMemory,
    Processes,
    ProcessInfo,
    ProcessListItem,
    ProcessMemoryUsage,
    ProcessUsage,
    StaticAsic,
    StaticBoard,
    StaticBus,
    StaticCacheInfoItem,
    StaticClockData,
    StaticDriver,
    StaticFrequencyLevels,
    StaticNuma,
    StaticPolicy,
    StaticSocPstate,
    StaticVbios,
    StaticVram,
    StaticXgmiPlpd,
    ValueUnit,
)
from nodescraper.utils import get_exception_details, get_exception_traceback


class AmdSmiCollector(InBandDataCollector[AmdSmiDataModel, None]):
    """Class for collection of inband tool amd-smi data."""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AmdSmiDataModel

    _amdsmi: Optional[Any] = None  # dynamic import

    def _amdsmi_mod(self) -> Any:
        """Check for amdsmi installation

        Returns:
            Any: local instance of amdsmi module
        """
        assert self._amdsmi is not None, "amdsmi module not bound"
        return self._amdsmi

    def _to_number(self, v: object) -> Optional[Union[int, float]]:
        """Helper function to return number from str, float or "N/A"

        Args:
            v (object): non number object

        Returns:
            Optional[Union[int, float]]: number version of input
        """
        if v in (None, "", "N/A"):
            return None
        try:
            if isinstance(v, (int, float)):
                return v
            if isinstance(v, str):
                s = v.strip()
                try:
                    return int(s)
                except Exception:
                    return float(s)
            return float(str(v))
        except Exception:
            return None

    def _valueunit(self, v: object, unit: str, *, required: bool = False) -> Optional[ValueUnit]:
        """Build ValueUnit instance from object

        Args:
            v (object): object to be turned into ValueUnit
            unit (str): unit of measurement
            required (bool, optional): bool to force instance creation. Defaults to False.

        Returns:
            Optional[ValueUnit]: ValueUnit Instance
        """
        n = self._to_number(v)
        if n is None:
            return ValueUnit(value=0, unit=unit) if required else None
        return ValueUnit(value=n, unit=unit)

    def _valueunit_req(self, v: object, unit: str) -> ValueUnit:
        """Helper function to force ValueUnit instance creation

        Args:
            v (object): object
            unit (str): unit of measurement

        Returns:
            ValueUnit: instance of ValueUnit
        """
        vu = self._valueunit(v, unit, required=True)
        assert vu is not None
        return vu

    def _normalize(self, val: object, default: str = "unknown", slot_type: bool = False) -> str:
        """Normalize strings

        Args:
            val (object): object
            default (str, optional): default option. Defaults to "unknown".
            slot_type (bool, optional): map to one of {'OAM','PCIE','CEM','Unknown'}. Defaults to False.

        Returns:
            str: normalized string
        """
        s = str(val).strip() if val is not None else ""
        if not s or s.upper() == "N/A":
            return "Unknown" if slot_type else default

        if slot_type:
            u = s.upper().replace(" ", "").replace("-", "")
            if u == "OAM":
                return "OAM"
            if u in {"PCIE", "PCIEXPRESS", "PCIEXP"} or u.startswith("PCIE"):
                return "PCIE"
            if u == "CEM":
                return "CEM"
            return "Unknown"

        return s

    def _bind_amdsmi_or_log(self) -> bool:
        """Bind to local amdsmi lib or log that it is not found

        Returns:
            bool: True if module is found, false otherwise
        """
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

    def _get_handles(self) -> list[Any]:
        """Get amdsmi handles

        Returns:
            list[Any]: list of processor handles
        """
        amdsmi = self._amdsmi_mod()
        try:
            return amdsmi.amdsmi_get_processor_handles()
        except amdsmi.AmdSmiException as e:  # type: ignore[attr-defined]
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_processor_handles failed",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return []

    def _get_amdsmi_data(self) -> Optional[AmdSmiDataModel]:
        """Fill in information for AmdSmi data model

        Returns:
            Optional[AmdSmiDataModel]: instance of the AmdSmi data model
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

    def _get_amdsmi_version(self) -> Optional[AmdSmiVersion]:
        """Check amdsmi library version

        Returns:
            Optional[AmdSmiVersion]: version of the library
        """
        amdsmi = self._amdsmi_mod()
        try:
            lib_ver = amdsmi.amdsmi_get_lib_version() or ""
            rocm_ver = amdsmi.amdsmi_get_rocm_version() or ""
        except amdsmi.AmdSmiException as e:  # type: ignore[attr-defined]
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

    def get_gpu_list(self) -> Optional[list[AmdSmiListItem]]:
        """Get GPU information from amdsmi lib

        Returns:
            Optional[list[AmdSmiListItem]]: list of GPU info items
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        out: list[AmdSmiListItem] = []

        def _to_int(x: Any, default: int = 0) -> int:
            try:
                return int(x)
            except Exception:
                return default

        for idx, h in enumerate(devices):
            bdf = self._smi_try(amdsmi.amdsmi_get_gpu_device_bdf, h, default="") or ""
            uuid = self._smi_try(amdsmi.amdsmi_get_gpu_device_uuid, h, default="") or ""
            kfd = self._smi_try(amdsmi.amdsmi_get_gpu_kfd_info, h, default={}) or {}
            partition_id = 0

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

    def get_process(self) -> Optional[list[Processes]]:
        """Get process information

        Returns:
            Optional[list[Processes]]: list of GPU processes
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        out: list[Processes] = []

        for idx, h in enumerate(devices):
            try:
                raw_list = self._smi_try(amdsmi.amdsmi_get_gpu_process_list, h, default=[]) or []
                plist: list[ProcessListItem] = []

                for entry in raw_list:
                    if not isinstance(entry, dict):
                        plist.append(ProcessListItem(process_info=str(entry)))
                        continue

                    name = entry.get("name", "N/A")
                    pid_val = entry.get("pid", 0)
                    try:
                        pid = int(pid_val) if pid_val not in (None, "") else 0
                    except Exception:
                        pid = 0

                    mem_vu = self._valueunit(entry.get("mem"), "B")

                    mu = entry.get("memory_usage") or {}
                    mem_usage = ProcessMemoryUsage(
                        gtt_mem=self._valueunit(mu.get("gtt_mem"), "B"),
                        cpu_mem=self._valueunit(mu.get("cpu_mem"), "B"),
                        vram_mem=self._valueunit(mu.get("vram_mem"), "B"),
                    )

                    eu = entry.get("engine_usage") or {}
                    usage = ProcessUsage(
                        gfx=self._valueunit(eu.get("gfx"), "ns"),
                        enc=self._valueunit(eu.get("enc"), "ns"),
                    )

                    cu_occ = self._valueunit(entry.get("cu_occupancy"), "")

                    try:
                        plist.append(
                            ProcessListItem(
                                process_info=ProcessInfo(
                                    name=str(name),
                                    pid=pid,
                                    mem=mem_vu,
                                    memory_usage=mem_usage,
                                    usage=usage,
                                    cu_occupancy=cu_occ,
                                )
                            )
                        )
                    except ValidationError as e:
                        self._log_event(
                            category=EventCategory.APPLICATION,
                            description="Failed to build ProcessListItem; skipping entry",
                            data={
                                "exception": get_exception_traceback(e),
                                "gpu_index": idx,
                                "entry": repr(entry),
                            },
                            priority=EventPriority.WARNING,
                        )
                        continue

                try:
                    out.append(Processes(gpu=idx, process_list=plist))
                except ValidationError as e:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Failed to build Processes",
                        data={"exception": get_exception_traceback(e), "gpu_index": idx},
                        priority=EventPriority.WARNING,
                    )
            except amdsmi.AmdSmiException as e:  # type: ignore[attr-defined]
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Process collection failed",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_partition(self) -> Optional[Partition]:
        """Check partition information

        Returns:
            Optional[Partition]: Partition data if available
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        memparts: list[PartitionMemory] = []
        computeparts: list[PartitionCompute] = []

        for idx, h in enumerate(devices):
            mem_pt = self._smi_try(amdsmi.amdsmi_get_gpu_memory_partition, h, default=None)
            comp_pt = self._smi_try(amdsmi.amdsmi_get_gpu_compute_partition, h, default=None)

            try:
                memparts.append(
                    PartitionMemory(gpu_id=idx, partition_type=cast(Optional[str], mem_pt))
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionMemory",
                    data={
                        "exception": get_exception_traceback(e),
                        "gpu_index": idx,
                        "data": mem_pt,
                    },
                    priority=EventPriority.WARNING,
                )

            try:
                computeparts.append(
                    PartitionCompute(gpu_id=idx, partition_type=cast(Optional[str], comp_pt))
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionCompute",
                    data={
                        "exception": get_exception_traceback(e),
                        "gpu_index": idx,
                        "data": comp_pt,
                    },
                    priority=EventPriority.WARNING,
                )

        try:
            return Partition(memory_partition=memparts, compute_partition=computeparts)
        except ValidationError as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build Partition",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.WARNING,
            )
            return None

    def get_firmware(self) -> Optional[list[Fw]]:
        """Get firmware information

        Returns:
            Optional[list[Fw]]: List of firmware info per GPU
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        out: list[Fw] = []

        for idx, h in enumerate(devices):
            raw = self._smi_try(amdsmi.amdsmi_get_fw_info, h, default=None)
            if (
                not isinstance(raw, dict)
                or "fw_list" not in raw
                or not isinstance(raw["fw_list"], list)
            ):
                continue

            items = raw["fw_list"]

            normalized: list[FwListItem] = []
            for e in items:
                if isinstance(e, dict):
                    fid = e.get("fw_name")
                    ver = e.get("fw_version")
                    normalized.append(
                        FwListItem(
                            fw_name="" if fid is None else str(fid),
                            fw_version="" if ver is None else str(ver),
                        )
                    )
                else:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Unrecognized firmware entry shape",
                        data={"entry_shape": repr(e)},
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

    def _smi_try(self, fn: Callable[..., Any], *a: Any, default: Any = None, **kw: Any) -> Any:
        """Helper function to check if amdsmi lib call is available

        Args:
            fn (Callable[..., Any]): amdsmi lib function to call
            *a (Any): variable positional arguments to pass to the function
            default (Any, optional): default return value. Defaults to None.
            **kw (Any): variable keyword arguments to pass to the function

        Returns:
            Any: result of function call or default value on error
        """
        amdsmi = self._amdsmi_mod()
        try:
            return fn(*a, **kw)
        except amdsmi.AmdSmiException as e:  # type: ignore[attr-defined]
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
            name = CODE2NAME.get(code, "unknown") if isinstance(code, int) else "unknown"

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

    def get_static(self) -> Optional[list[AmdSmiStatic]]:
        """Get Static info from amdsmi lib

        Returns:
            Optional[list[AmdSmiStatic]]: list of AmdSmiStatic instances or empty list
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        if not devices:
            return []

        pcie_fn = getattr(amdsmi, "amdsmi_get_pcie_info", None)

        out: list[AmdSmiStatic] = []

        for idx, h in enumerate(devices):
            board = self._smi_try(amdsmi.amdsmi_get_gpu_board_info, h, default={}) or {}
            asic = self._smi_try(amdsmi.amdsmi_get_gpu_asic_info, h, default={}) or {}
            bdf = self._smi_try(amdsmi.amdsmi_get_gpu_device_bdf, h, default="") or ""
            kfd = self._smi_try(amdsmi.amdsmi_get_gpu_kfd_info, h, default={}) or {}

            # Bus / PCIe
            bus = StaticBus(
                bdf=bdf,
                max_pcie_width=None,
                max_pcie_speed=None,
                pcie_interface_version="unknown",
                slot_type="Unknown",
            )

            if callable(pcie_fn):
                p = self._smi_try(pcie_fn, h, default={}) or {}
                d = p.get("pcie_static", p) if isinstance(p, dict) else {}

                if isinstance(d, dict):
                    max_w = d.get("max_pcie_width")
                    max_s = d.get("max_pcie_speed")
                    pcie_ver = d.get("pcie_interface_version")

                    # MT/s -> GT/s
                    ms_val = self._to_number(max_s)
                    gtps = (
                        (cast(float, ms_val) / 1000.0)
                        if (isinstance(ms_val, (int, float)) and ms_val >= 1000)
                        else ms_val
                    )

                    bus = StaticBus(
                        bdf=bdf,
                        max_pcie_width=self._valueunit(max_w, "x"),
                        max_pcie_speed=self._valueunit(gtps, "GT/s"),
                        pcie_interface_version=self._normalize(pcie_ver),
                        slot_type=self._normalize(d.get("slot_type"), slot_type=True),
                    )

            # ASIC
            asic_model = StaticAsic(
                market_name=self._normalize(
                    asic.get("market_name") or asic.get("asic_name"), default=""
                ),
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

            # Driver
            driver_model = None
            drv_fn = getattr(amdsmi, "amdsmi_get_gpu_driver_info", None)
            if callable(drv_fn):
                drv = self._smi_try(drv_fn, h, default={}) or {}
                driver_model = StaticDriver(
                    name=self._normalize(drv.get("driver_name"), default="unknown"),
                    version=self._normalize(drv.get("driver_version"), default="unknown"),
                )

            # VBIOS
            vb = {
                k: board[k]
                for k in ("vbios_name", "vbios_build_date", "vbios_part_number", "vbios_version")
                if k in board
            }
            vbios_model: Optional[StaticVbios] = None
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
            else:
                numa_node = 0
            affinity = 0
            numa_model = StaticNuma(node=numa_node, affinity=affinity)

            # VRAM
            vram_type = str(asic.get("vram_type", "") or "unknown")
            vram_vendor = asic.get("vram_vendor")
            vram_bits = asic.get("vram_bit_width")
            vram_size_b: Optional[int] = None
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
                size=self._valueunit(vram_size_b, "B"),
                bit_width=self._valueunit(vram_bits, "bit"),
                max_bandwidth=None,
            )

            soc_pstate_model = self._get_soc_pstate(h)
            xgmi_plpd_model = self._get_xgmi_plpd(h)
            cache_info_model = self._get_cache_info(h)
            clock_model = self._get_clock(h)

            try:
                out.append(
                    AmdSmiStatic(
                        gpu=idx,
                        asic=asic_model,
                        bus=bus,
                        vbios=vbios_model,
                        limit=None,
                        driver=driver_model,
                        board=board_model,
                        soc_pstate=soc_pstate_model,
                        xgmi_plpd=xgmi_plpd_model,
                        process_isolation="",
                        numa=numa_model,
                        vram=vram_model,
                        cache_info=cache_info_model,
                        partition=None,
                        clock=clock_model,
                    )
                )
            except ValidationError as e:
                self.logger.error(e)
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiStatic",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def _get_soc_pstate(self, handle: Any) -> Optional[StaticSocPstate]:
        """SOC pstate check

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticSocPstate]: StaticSocPstate instance or None
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_soc_pstate", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_soc_pstate not exposed by amdsmi build",
                priority=EventPriority.INFO,
            )
            return None

        data = self._smi_try(fn, handle, default=None)
        if not isinstance(data, dict):
            return None

        try:
            num_supported = int(data.get("num_supported", 0) or 0)
        except Exception:
            num_supported = 0
        try:
            current_id = int(data.get("current_id", 0) or 0)
        except Exception:
            current_id = 0

        policies_raw = data.get("policies") or []
        policies: list[StaticPolicy] = []
        if isinstance(policies_raw, list):
            for p in policies_raw:
                if not isinstance(p, dict):
                    continue
                pid = p.get("policy_id", 0)
                desc = p.get("policy_description", "")
                try:
                    policies.append(
                        StaticPolicy(
                            policy_id=int(pid) if pid not in (None, "") else 0,
                            policy_description=str(desc),
                        )
                    )
                except ValidationError:
                    continue

        if not num_supported and not current_id and not policies:
            return None

        try:
            return StaticSocPstate(
                num_supported=num_supported,
                current_id=current_id,
                policies=policies,
            )
        except ValidationError:
            return None

    def _get_xgmi_plpd(self, handle: Any) -> Optional[StaticXgmiPlpd]:
        """Check XGMI plpd

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticXgmiPlpd]: StaticXgmiPlpd instance or None
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_xgmi_plpd", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="XGMI PLPD not exposed by this amdsmi build",
                priority=EventPriority.INFO,
            )
            return None

        data = self._smi_try(fn, handle, default=None)
        if not isinstance(data, dict):
            return None

        try:
            num_supported = int(data.get("num_supported", 0) or 0)
        except Exception:
            num_supported = 0
        try:
            current_id = int(data.get("current_id", 0) or 0)
        except Exception:
            current_id = 0

        plpds_raw = data.get("plpds") or []
        plpds: list[StaticPolicy] = []
        if isinstance(plpds_raw, list):
            for p in plpds_raw:
                if not isinstance(p, dict):
                    continue
                pid = p.get("policy_id", 0)
                desc = p.get("policy_description", "")
                try:
                    plpds.append(
                        StaticPolicy(
                            policy_id=int(pid) if pid not in (None, "") else 0,
                            policy_description=str(desc),
                        )
                    )
                except ValidationError:
                    continue

        if not num_supported and not current_id and not plpds:
            return None

        try:
            return StaticXgmiPlpd(
                num_supported=num_supported,
                current_id=current_id,
                plpds=plpds,
            )
        except ValidationError:
            return None

    def _get_cache_info(self, handle: Any) -> list[StaticCacheInfoItem]:
        """Check cache info

        Args:
            handle (Any): GPU device handle

        Returns:
            list[StaticCacheInfoItem]: list of StaticCacheInfoItem instances
        """
        amdsmi = self._amdsmi_mod()
        raw = self._smi_try(amdsmi.amdsmi_get_gpu_cache_info, handle, default=None)
        if not isinstance(raw, dict) or not isinstance(raw.get("cache"), list):
            return []

        items = raw["cache"]

        def _as_list_str(v: Any) -> list[str]:
            if isinstance(v, list):
                return [str(x) for x in v]
            if isinstance(v, str):
                parts = [p.strip() for p in v.replace(";", ",").split(",")]
                return [p for p in parts if p]
            return []

        out: list[StaticCacheInfoItem] = []
        for e in items:
            if not isinstance(e, dict):
                continue

            cache_level = self._valueunit_req(e.get("cache_level"), "")
            max_num_cu_shared = self._valueunit_req(e.get("max_num_cu_shared"), "")
            num_cache_instance = self._valueunit_req(e.get("num_cache_instance"), "")
            cache_size = self._valueunit(e.get("cache_size"), "", required=False)
            cache_props = _as_list_str(e.get("cache_properties"))

            lvl_val = cache_level.value
            cache_label_val = (
                f"Label_{int(lvl_val) if isinstance(lvl_val, (int, float)) else lvl_val}"
            )
            cache_label = ValueUnit(value=cache_label_val, unit="")

            try:
                out.append(
                    StaticCacheInfoItem(
                        cache=cache_label,
                        cache_properties=cache_props,
                        cache_size=cache_size,
                        cache_level=cache_level,
                        max_num_cu_shared=max_num_cu_shared,
                        num_cache_instance=num_cache_instance,
                    )
                )
            except ValidationError as ve:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Bad cache info entry from AMDSMI; skipping",
                    data={"entry": repr(e), "exception": get_exception_traceback(ve)},
                    priority=EventPriority.WARNING,
                )
                continue

        return out

    def _get_clock(self, handle: Any) -> Optional[StaticClockData]:
        """Get clock info

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticClockData]: StaticClockData instance or None
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_clk_freq", None)
        clk_type = getattr(amdsmi, "AmdSmiClkType", None)
        if not callable(fn) or clk_type is None or not hasattr(clk_type, "SYS"):
            return None

        data = self._smi_try(fn, handle, clk_type.SYS, default=None)
        if not isinstance(data, dict):
            return None

        freqs_raw = data.get("frequency")
        if not isinstance(freqs_raw, list) or not freqs_raw:
            return None

        def _to_mhz(v: object) -> Optional[int]:
            x = self._to_number(v)
            if x is None:
                return None
            xf = float(x)
            if xf >= 1e7:
                return int(round(xf / 1_000_000.0))
            if xf >= 1e4:
                return int(round(xf / 1_000.0))
            return int(round(xf))

        freqs_mhz: list[int] = []
        for v in freqs_raw:
            mhz = _to_mhz(v)
            if mhz is not None:
                freqs_mhz.append(mhz)

        if not freqs_mhz:
            return None

        def _fmt(n: Optional[int]) -> Optional[str]:
            return None if n is None else f"{n} MHz"

        level0: str = _fmt(freqs_mhz[0]) or "0 MHz"
        level1: Optional[str] = _fmt(freqs_mhz[1]) if len(freqs_mhz) > 1 else None
        level2: Optional[str] = _fmt(freqs_mhz[2]) if len(freqs_mhz) > 2 else None

        cur_raw = data.get("current")
        current: Optional[int]
        if isinstance(cur_raw, (int, float)):
            current = int(cur_raw)
        elif isinstance(cur_raw, str) and cur_raw.strip() and cur_raw.upper() != "N/A":
            try:
                current = int(cur_raw.strip())
            except Exception:
                current = None
        else:
            current = None

        try:
            levels = StaticFrequencyLevels.model_validate(
                {"Level 0": level0, "Level 1": level1, "Level 2": level2}
            )

            return StaticClockData(frequency=levels, current=current)
        except ValidationError:
            return None

    def collect_data(
        self,
        args: Any = None,
    ) -> tuple[TaskResult, Optional[AmdSmiDataModel]]:
        """Collect AmdSmi data from system

        Args:
            args (Any, optional): optional arguments for data collection. Defaults to None.

        Returns:
            tuple[TaskResult, Optional[AmdSmiDataModel]]: task result and collected data model
        """

        if not self._bind_amdsmi_or_log():
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        amdsmi = self._amdsmi_mod()
        try:
            amdsmi.amdsmi_init(amdsmi.AmdSmiInitFlags.INIT_AMD_GPUS)  # type: ignore[attr-defined]
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
                amdsmi.amdsmi_shut_down()
            except Exception:
                pass
