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
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiVersion,
    BadPages,
    Fw,
    FwListItem,
    MetricClockData,
    MetricEccTotals,
    MetricEnergy,
    MetricFan,
    MetricMemUsage,
    MetricPcie,
    MetricPower,
    MetricTemperature,
    MetricThrottle,
    MetricThrottleVu,
    MetricUsage,
    MetricVoltageCurve,
    PageData,
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
    StaticLimit,
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
            bad_pages = self.get_bad_pages()
            processes = self.get_process()
            partition = self.get_partition()
            firmware = self.get_firmware()
            gpu_list = self.get_gpu_list()
            statics = self.get_static()
            metric = self.get_metric()
        except Exception as e:
            self.logger.error(e)
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
                bad_pages=bad_pages,
                gpu_list=gpu_list,
                process=processes,
                partition=partition,
                firmware=firmware,
                static=statics,
                metric=metric,
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

                    raw_name = entry.get("name", None)
                    name = (
                        None
                        if (raw_name is None or str(raw_name).strip().upper() == "N/A")
                        else str(raw_name)
                    )

                    pid_val = entry.get("pid", 0)
                    try:
                        pid = int(pid_val) if pid_val not in (None, "") else 0
                    except Exception:
                        pid = 0

                    # memory_usage block
                    mu = entry.get("memory_usage") or {}
                    gtt_mem_vu = self._valueunit(mu.get("gtt_mem"), "B")
                    cpu_mem_vu = self._valueunit(mu.get("cpu_mem"), "B")
                    vram_mem_vu = self._valueunit(mu.get("vram_mem"), "B")

                    # mem
                    mem_vu = self._valueunit(entry.get("mem"), "B")
                    if mem_vu is None and vram_mem_vu is not None:
                        mem_vu = vram_mem_vu

                    if (not mu) and mem_vu is not None and vram_mem_vu is None:
                        vram_mem_vu = mem_vu

                    mem_usage = ProcessMemoryUsage(
                        gtt_mem=gtt_mem_vu,
                        cpu_mem=cpu_mem_vu,
                        vram_mem=vram_mem_vu,
                    )

                    # engine_usage
                    eu = entry.get("engine_usage") or {}
                    gfx_vu = self._valueunit(eu.get("gfx"), "ns") or self._valueunit(0, "ns")
                    enc_vu = self._valueunit(eu.get("enc"), "ns") or self._valueunit(0, "ns")
                    usage = ProcessUsage(gfx=gfx_vu, enc=enc_vu)

                    cu_occ = self._valueunit(entry.get("cu_occupancy"), "")

                    try:
                        plist.append(
                            ProcessListItem(
                                process_info=ProcessInfo(
                                    name=name if name is not None else "N/A",
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
            fn_name = getattr(fn, "__name__", str(fn))
            self.logger.warning(
                "%s(%s) raised AmdSmiException: %s",
                fn_name,
                ", ".join(repr(x) for x in a),
                e,
            )

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

            common_data = {
                "function": fn_name,
                "args": [repr(x) for x in a],
                "status_name": name,
                "status_code": code,
                "exception": get_exception_traceback(e),
            }

            if name in ("AMDSMI_STATUS_NOT_SUPPORTED", "AMDSMI_STATUS_NOT_FOUND"):
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"{fn_name} not supported on this device/mode (status={name}, code={code})",
                    data=common_data,
                    priority=EventPriority.WARNING,
                )
                return default

            if name == "AMDSMI_STATUS_PERMISSION":
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=(
                        f"{fn_name} permission denied "
                        f"(need access to /dev/kfd & render nodes, or root for RAS). "
                        f"status={name}, code={code}"
                    ),
                    data=common_data,
                    priority=EventPriority.WARNING,
                )
                return default

            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"{fn_name} failed (status={name}, code={code})",
                data=common_data,
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

            # NUMA
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

            # Calculate VRAM max bandwidth if possible
            max_bandwidth = None
            if vram_bits and kfd.get("memory_max_frequency"):
                try:
                    mem_freq_mhz = float(kfd["memory_max_frequency"])
                    # Bandwidth (GB/s) = (bit_width * frequency_MHz) / 8000 Note: is this correct?
                    bandwidth_gbs = (float(vram_bits) * mem_freq_mhz) / 8000.0
                    max_bandwidth = self._valueunit(bandwidth_gbs, "GB/s")
                except Exception:
                    pass

            vram_model = StaticVram(
                type=vram_type,
                vendor=None if vram_vendor in (None, "", "N/A") else str(vram_vendor),
                size=self._valueunit(vram_size_b, "B"),
                bit_width=self._valueunit(vram_bits, "bit"),
                max_bandwidth=max_bandwidth,
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
                        limit=self._get_limit_info(h),
                        driver=driver_model,
                        board=board_model,
                        soc_pstate=soc_pstate_model,
                        xgmi_plpd=xgmi_plpd_model,
                        process_isolation="",
                        numa=numa_model,
                        vram=vram_model,
                        cache_info=cache_info_model,
                        partition=None,  # Note: ?
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
        """Get SOC P-state (performance state) policy information for a GPU device.

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticSocPstate]: SOC P-state policy data or None if unavailable
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_soc_pstate", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_soc_pstate not exposed by amdsmi build",
                priority=EventPriority.WARNING,
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
        """Get XGMI Per-Link Power Down (PLPD) policy for a GPU device.

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticXgmiPlpd]: XGMI PLPD policy data or None if unavailable
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_xgmi_plpd", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="XGMI PLPD not exposed by this amdsmi build",
                priority=EventPriority.WARNING,
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
        """Get GPU cache hierarchy information (L1, L2, L3, etc.).

        Args:
            handle (Any): GPU device handle

        Returns:
            list[StaticCacheInfoItem]: List of cache info items for each cache level
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

    def _get_limit_info(self, handle: Any) -> Optional[StaticLimit]:
        """Get power cap and temperature limit information.

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticLimit]: StaticLimit instance or None
        """
        amdsmi = self._amdsmi_mod()
        fn = getattr(amdsmi, "amdsmi_get_power_cap_info", None)
        if not callable(fn):
            return None

        data = self._smi_try(fn, handle, default=None)
        if not isinstance(data, dict):
            return None

        return StaticLimit(
            max_power=self._valueunit(data.get("power_cap"), "W"),
            min_power=self._valueunit(data.get("min_power_cap"), "W"),
            socket_power=self._valueunit(data.get("default_power_cap"), "W"),
            slowdown_edge_temperature=self._valueunit(data.get("slowdown_temp"), "C"),
            slowdown_hotspot_temperature=self._valueunit(data.get("slowdown_mem_temp"), "C"),
            slowdown_vram_temperature=self._valueunit(data.get("slowdown_vram_temp"), "C"),
            shutdown_edge_temperature=self._valueunit(data.get("shutdown_temp"), "C"),
            shutdown_hotspot_temperature=self._valueunit(data.get("shutdown_mem_temp"), "C"),
            shutdown_vram_temperature=self._valueunit(data.get("shutdown_vram_temp"), "C"),
        )

    def _get_clock(self, handle: Any) -> Optional[StaticClockData]:
        """Get clock info using amdsmi_get_clock_info or fallback to amdsmi_get_clk_freq

        Args:
            handle (Any): GPU device handle

        Returns:
            Optional[StaticClockData]: StaticClockData instance or None
        """
        amdsmi = self._amdsmi_mod()
        clk_type = getattr(amdsmi, "AmdSmiClkType", None)

        if clk_type is None or not hasattr(clk_type, "SYS"):
            return None

        # Try amdsmi_get_clock_info API first
        clock_info_fn = getattr(amdsmi, "amdsmi_get_clock_info", None)
        if callable(clock_info_fn):
            data = self._smi_try(clock_info_fn, handle, clk_type.SYS, default=None)
            if isinstance(data, dict):
                freqs_raw = data.get("clk_freq") or data.get("frequency")
                if isinstance(freqs_raw, list) and freqs_raw:
                    return self._process_clock_data(data, freqs_raw)

        # Fallback to amdsmi_get_clk_freq API
        fn = getattr(amdsmi, "amdsmi_get_clk_freq", None)
        if not callable(fn):
            return None

        data = self._smi_try(fn, handle, clk_type.SYS, default=None)
        if not isinstance(data, dict):
            return None

        freqs_raw = data.get("frequency")
        if not isinstance(freqs_raw, list) or not freqs_raw:
            return None

        return self._process_clock_data(data, freqs_raw)

    def _process_clock_data(self, data: dict, freqs_raw: list) -> Optional[StaticClockData]:
        """Process clock frequency data into StaticClockData model.

        Args:
            data (dict): Raw clock data from amdsmi API
            freqs_raw (list): List of frequency values

        Returns:
            Optional[StaticClockData]: StaticClockData instance or None
        """

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

    def get_bad_pages(self) -> Optional[list[BadPages]]:
        """Collect bad page info per GPU and map to BadPages/PageData models.

        Returns:
            Optional[list[BadPages]]: List of bad pages (one per GPU) or None if no devices
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        if not devices:
            return None

        out: list[BadPages] = []

        for idx, h in enumerate(devices):
            raw = self._smi_try(amdsmi.amdsmi_get_gpu_bad_page_info, h, default=[]) or []
            pages: list[PageData] = []

            if isinstance(raw, list):
                for entry in raw:
                    if not isinstance(entry, dict):
                        continue

                    pa = entry.get("page_address")
                    ps = entry.get("page_size")
                    st = entry.get("status")
                    val = entry.get("value")

                    page_address: Union[int, str]
                    if isinstance(pa, (int, str)):
                        page_address = pa
                    else:
                        page_address = str(pa)

                    page_size: Union[int, str]
                    if isinstance(ps, (int, str)):
                        page_size = ps
                    else:
                        page_size = str(ps)

                    status = "" if st in (None, "N/A") else str(st)

                    value_i: Optional[int] = None
                    if isinstance(val, int):
                        value_i = val
                    elif isinstance(val, str):
                        s = val.strip()
                        try:
                            value_i = int(s, 0)
                        except Exception:
                            value_i = None

                    try:
                        pages.append(
                            PageData(
                                page_address=page_address,
                                page_size=page_size,
                                status=status,
                                value=value_i,
                            )
                        )
                    except ValidationError as e:
                        self._log_event(
                            category=EventCategory.APPLICATION,
                            description="Failed to build PageData; skipping entry",
                            data={
                                "exception": get_exception_traceback(e),
                                "gpu_index": idx,
                                "entry": repr(entry),
                            },
                            priority=EventPriority.WARNING,
                        )
                        continue

            try:
                out.append(BadPages(gpu=idx, retired=pages))
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build BadPages",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_metric(self) -> Optional[list[AmdSmiMetric]]:
        """Collect runtime metric data from all GPU devices.

        Collects usage, power, temperature, clocks, PCIe, fan, memory, ECC,
        throttle, and voltage curve data from amdsmi_get_gpu_metrics_info.

        Returns:
            Optional[list[AmdSmiMetric]]: List of metric data per GPU or None if no devices
        """
        amdsmi = self._amdsmi_mod()
        devices = self._get_handles()
        out: list[AmdSmiMetric] = []

        def _to_int_or_none(v: object) -> Optional[int]:
            n = self._to_number(v)
            if n is None:
                return None
            try:
                return int(n)
            except Exception:
                try:
                    return int(float(n))
                except Exception:
                    return None

        def _as_list(v: object) -> list[object]:
            if isinstance(v, list):
                return v
            return (
                [] if v in (None, "N/A") else [v] if not isinstance(v, (dict, tuple, set)) else []
            )

        for idx, h in enumerate(devices):
            raw = self._smi_try(amdsmi.amdsmi_get_gpu_metrics_info, h, default=None)

            if not isinstance(raw, dict):
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="amdsmi_get_gpu_metrics_info returned no dict; using empty metric",
                    data={"gpu_index": idx, "type": type(raw).__name__},
                    priority=EventPriority.WARNING,
                )
                out.append(self._empty_metric(idx))
                continue

            try:
                # Usage
                usage = MetricUsage(
                    gfx_activity=self._valueunit(raw.get("average_gfx_activity"), "%"),
                    umc_activity=self._valueunit(raw.get("average_umc_activity"), "%"),
                    mm_activity=self._valueunit(raw.get("average_mm_activity"), "%"),
                    vcn_activity=[
                        self._valueunit(v, "%") for v in _as_list(raw.get("vcn_activity"))
                    ],
                    jpeg_activity=[
                        self._valueunit(v, "%") for v in _as_list(raw.get("jpeg_activity"))
                    ],
                    gfx_busy_inst=None,  # Note: note avilable?
                    jpeg_busy=None,  # Note: note avilable?
                    vcn_busy=None,  # Note: note avilable?
                )

                # Power / Energy
                # Get power from metrics_info
                socket_power_val = self._valueunit(raw.get("average_socket_power"), "W")

                # Try amdsmi_get_power_info if available and metrics is missing
                if socket_power_val is None:
                    power_info_fn = getattr(amdsmi, "amdsmi_get_power_info", None)
                    if callable(power_info_fn):
                        power_data = self._smi_try(power_info_fn, h, default=None)
                        if isinstance(power_data, dict):
                            socket_power_val = self._valueunit(
                                power_data.get("current_socket_power")
                                or power_data.get("average_socket_power"),
                                "W",
                            )

                power = MetricPower(
                    socket_power=socket_power_val,
                    gfx_voltage=self._valueunit(raw.get("voltage_gfx"), "mV"),
                    soc_voltage=self._valueunit(raw.get("voltage_soc"), "mV"),
                    mem_voltage=self._valueunit(raw.get("voltage_mem"), "mV"),
                    throttle_status=(
                        str(raw.get("throttle_status"))
                        if raw.get("throttle_status") is not None
                        else None
                    ),
                    power_management=self._normalize(
                        raw.get("indep_throttle_status"), default="unknown"
                    ),
                )
                energy = MetricEnergy(
                    total_energy_consumption=self._valueunit(raw.get("energy_accumulator"), "uJ")
                )

                # Temperature
                temperature = MetricTemperature(
                    edge=self._valueunit(raw.get("temperature_edge"), "C"),
                    hotspot=self._valueunit(raw.get("temperature_hotspot"), "C"),
                    mem=self._valueunit(raw.get("temperature_mem"), "C"),
                )

                # PCIe
                speed_raw = self._to_number(raw.get("pcie_link_speed"))
                speed_gtps = (
                    float(speed_raw) / 10.0 if isinstance(speed_raw, (int, float)) else None
                )

                # Get PCIe throughput
                throughput_fn = getattr(amdsmi, "amdsmi_get_gpu_pci_throughput", None)
                bandwidth_sent = None
                bandwidth_received = None
                if callable(throughput_fn):
                    throughput_data = self._smi_try(throughput_fn, h, default=None)
                    if isinstance(throughput_data, dict):
                        bandwidth_sent = _to_int_or_none(throughput_data.get("sent"))
                        bandwidth_received = _to_int_or_none(throughput_data.get("received"))

                pcie = MetricPcie(
                    width=_to_int_or_none(raw.get("pcie_link_width")),
                    speed=self._valueunit(speed_gtps, "GT/s"),
                    bandwidth=self._valueunit(raw.get("pcie_bandwidth_inst"), "GB/s"),
                    replay_count=_to_int_or_none(raw.get("pcie_replay_count_acc")),
                    l0_to_recovery_count=_to_int_or_none(raw.get("pcie_l0_to_recov_count_acc")),
                    replay_roll_over_count=_to_int_or_none(raw.get("pcie_replay_rover_count_acc")),
                    nak_sent_count=_to_int_or_none(raw.get("pcie_nak_sent_count_acc")),
                    nak_received_count=_to_int_or_none(raw.get("pcie_nak_rcvd_count_acc")),
                    current_bandwidth_sent=bandwidth_sent,
                    current_bandwidth_received=bandwidth_received,
                    max_packet_size=None,
                    lc_perf_other_end_recovery=None,
                )

                # Clocks from clock_info API
                clock_info_fn = getattr(amdsmi, "amdsmi_get_clock_info", None)
                clk_type = getattr(amdsmi, "AmdSmiClkType", None)
                clock_ranges = {}

                if callable(clock_info_fn) and clk_type is not None:
                    for clk_name, clk_enum_name in [
                        ("GFX", "GFX"),
                        ("SOC", "SYS"),
                        ("UCLK", "MEM"),
                        ("VCLK0", "VCLK0"),
                        ("DCLK0", "DCLK0"),
                        ("VCLK1", "VCLK1"),
                        ("DCLK1", "DCLK1"),
                    ]:
                        clk_enum = getattr(clk_type, clk_enum_name, None)
                        if clk_enum is not None:
                            clk_data = self._smi_try(clock_info_fn, h, clk_enum, default=None)
                            if isinstance(clk_data, dict):
                                clock_ranges[clk_name] = {
                                    "min": clk_data.get("min_clk"),
                                    "max": clk_data.get("max_clk"),
                                    "sleep": clk_data.get("sleep_clk")
                                    or clk_data.get("deep_sleep_clk"),
                                }

                def _clk(
                    cur_key: str,
                    clk_name: str = "",
                    raw: dict = raw,
                    clock_ranges: dict = clock_ranges,
                ) -> MetricClockData:
                    ranges = clock_ranges.get(clk_name, {})
                    return MetricClockData(
                        clk=self._valueunit(raw.get(cur_key), "MHz"),
                        min_clk=self._valueunit(ranges.get("min"), "MHz") if ranges else None,
                        max_clk=self._valueunit(ranges.get("max"), "MHz") if ranges else None,
                        clk_locked=(
                            raw.get("gfxclk_lock_status") if cur_key == "current_gfxclk" else None
                        ),
                        deep_sleep=ranges.get("sleep") if ranges else None,
                    )

                clock: dict[str, MetricClockData] = {
                    "GFX": _clk("current_gfxclk", "GFX"),
                    "SOC": _clk("current_socclk", "SOC"),
                    "UCLK": _clk("current_uclk", "UCLK"),
                    "VCLK0": _clk("current_vclk0", "VCLK0"),
                    "DCLK0": _clk("current_dclk0", "DCLK0"),
                    "VCLK1": _clk("current_vclk1", "VCLK1"),
                    "DCLK1": _clk("current_dclk1", "DCLK1"),
                }

                # Fan
                fan_rpm = self._valueunit(raw.get("current_fan_speed"), "RPM")

                # Get fan speed as percentage
                fan_speed_fn = getattr(amdsmi, "amdsmi_get_gpu_fan_speed", None)
                fan_speed_pct = None
                if callable(fan_speed_fn):
                    fan_speed_data = self._smi_try(fan_speed_fn, h, 0, default=None)
                    if isinstance(fan_speed_data, (int, float)):
                        fan_speed_pct = self._valueunit(fan_speed_data, "%")

                # Get max fan speed
                fan_max_fn = getattr(amdsmi, "amdsmi_get_gpu_fan_speed_max", None)
                fan_max_rpm = None
                if callable(fan_max_fn):
                    fan_max_data = self._smi_try(fan_max_fn, h, 0, default=None)
                    if isinstance(fan_max_data, (int, float)):
                        fan_max_rpm = self._valueunit(fan_max_data, "RPM")

                fan = MetricFan(
                    rpm=fan_rpm,
                    speed=fan_speed_pct,
                    max=fan_max_rpm,
                    usage=None,
                )

                # Voltage curve
                voltage_curve = self._get_voltage_curve(h) or self._empty_voltage_curve()

                # Memory usage
                total_vram_vu: Optional[ValueUnit] = None
                used_vram_vu: Optional[ValueUnit] = None
                free_vram_vu: Optional[ValueUnit] = None

                vram_usage = self._smi_try(amdsmi.amdsmi_get_gpu_vram_usage, h, default=None)
                if isinstance(vram_usage, dict):
                    used_vram_vu = self._valueunit(vram_usage.get("vram_used"), "B")
                    total_vram_vu = self._valueunit(vram_usage.get("vram_total"), "B")

                mem_enum = getattr(amdsmi, "AmdSmiMemoryType", None)
                vis_total_vu: Optional[ValueUnit] = None
                vis_used_vu: Optional[ValueUnit] = None
                vis_free_vu: Optional[ValueUnit] = None
                gtt_total_vu: Optional[ValueUnit] = None
                gtt_used_vu: Optional[ValueUnit] = None
                gtt_free_vu: Optional[ValueUnit] = None

                mem_usage_fn = getattr(amdsmi, "amdsmi_get_gpu_memory_usage", None)

                if mem_enum is not None:
                    if total_vram_vu is None:
                        vram_total_alt = self._smi_try(
                            amdsmi.amdsmi_get_gpu_memory_total, h, mem_enum.VRAM, default=None
                        )
                        if vram_total_alt is not None:
                            total_vram_vu = self._valueunit(vram_total_alt, "B")

                    # Visible VRAM total and usage
                    vis_total = self._smi_try(
                        amdsmi.amdsmi_get_gpu_memory_total, h, mem_enum.VIS_VRAM, default=None
                    )
                    if vis_total is not None:
                        vis_total_vu = self._valueunit(vis_total, "B")

                        # Get visible VRAM usage
                        if callable(mem_usage_fn):
                            vis_used = self._smi_try(
                                mem_usage_fn, h, mem_enum.VIS_VRAM, default=None
                            )
                            if vis_used is not None:
                                vis_used_vu = self._valueunit(vis_used, "B")
                                # Calculate free
                                try:
                                    free_val = max(0.0, float(vis_total) - float(vis_used))
                                    vis_free_vu = self._valueunit(free_val, "B")
                                except Exception:
                                    pass

                    # GTT total and usage
                    gtt_total = self._smi_try(
                        amdsmi.amdsmi_get_gpu_memory_total, h, mem_enum.GTT, default=None
                    )
                    if gtt_total is not None:
                        gtt_total_vu = self._valueunit(gtt_total, "B")

                        # Get GTT usage
                        if callable(mem_usage_fn):
                            gtt_used = self._smi_try(mem_usage_fn, h, mem_enum.GTT, default=None)
                            if gtt_used is not None:
                                gtt_used_vu = self._valueunit(gtt_used, "B")
                                # Calculate free
                                try:
                                    free_val = max(0.0, float(gtt_total) - float(gtt_used))
                                    gtt_free_vu = self._valueunit(free_val, "B")
                                except Exception:
                                    pass

                # Compute free VRAM if possible
                if free_vram_vu is None and total_vram_vu is not None and used_vram_vu is not None:
                    try:
                        free_num = max(0.0, float(total_vram_vu.value) - float(used_vram_vu.value))
                        free_vram_vu = self._valueunit(free_num, "B")
                    except Exception:
                        pass

                # Build mem_usage
                mem_usage = MetricMemUsage(
                    total_vram=total_vram_vu,
                    used_vram=used_vram_vu,
                    free_vram=free_vram_vu,
                    total_visible_vram=vis_total_vu,
                    used_visible_vram=vis_used_vu,
                    free_visible_vram=vis_free_vu,
                    total_gtt=gtt_total_vu,
                    used_gtt=gtt_used_vu,
                    free_gtt=gtt_free_vu,
                )

                # ECC totals
                ecc_raw = self._smi_try(amdsmi.amdsmi_get_gpu_total_ecc_count, h, default=None)
                if isinstance(ecc_raw, dict):
                    ecc = MetricEccTotals(
                        total_correctable_count=_to_int_or_none(ecc_raw.get("correctable_count")),
                        total_uncorrectable_count=_to_int_or_none(
                            ecc_raw.get("uncorrectable_count")
                        ),
                        total_deferred_count=_to_int_or_none(ecc_raw.get("deferred_count")),
                        cache_correctable_count=None,
                        cache_uncorrectable_count=None,
                    )
                else:
                    ecc = MetricEccTotals(
                        total_correctable_count=None,
                        total_uncorrectable_count=None,
                        total_deferred_count=None,
                        cache_correctable_count=None,
                        cache_uncorrectable_count=None,
                    )

                # Throttle
                throttle = self.get_throttle(h) or MetricThrottle()

                out.append(
                    AmdSmiMetric(
                        gpu=idx,
                        usage=usage,
                        power=power,
                        clock=clock,
                        temperature=temperature,
                        pcie=pcie,
                        ecc=ecc,
                        ecc_blocks={},
                        fan=fan,
                        voltage_curve=voltage_curve,
                        perf_level=None,
                        xgmi_err=None,
                        energy=energy,
                        mem_usage=mem_usage,
                        throttle=throttle,
                    )
                )
            except ValidationError as e:
                self.logger.warning(e)
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiMetric; using empty metric",
                    data={"exception": get_exception_traceback(e), "gpu_index": idx},
                    priority=EventPriority.WARNING,
                )
                out.append(self._empty_metric(idx))

        return out

    def _empty_metric(self, gpu_idx: int) -> AmdSmiMetric:
        """Create an empty/default AmdSmiMetric instance when data collection fails.

        Args:
            gpu_idx (int): GPU index

        Returns:
            AmdSmiMetric: Metric instance with all fields set to None or empty values
        """
        return AmdSmiMetric(
            gpu=gpu_idx,
            usage=MetricUsage(
                gfx_activity=None,
                umc_activity=None,
                mm_activity=None,
                vcn_activity=[],
                jpeg_activity=[],
                gfx_busy_inst=None,
                jpeg_busy=None,
                vcn_busy=None,
            ),
            power=MetricPower(
                socket_power=None,
                gfx_voltage=None,
                soc_voltage=None,
                mem_voltage=None,
                throttle_status=None,
                power_management=None,
            ),
            clock={},
            temperature=MetricTemperature(edge=None, hotspot=None, mem=None),
            pcie=MetricPcie(
                width=None,
                speed=None,
                bandwidth=None,
                replay_count=None,
                l0_to_recovery_count=None,
                replay_roll_over_count=None,
                nak_sent_count=None,
                nak_received_count=None,
                current_bandwidth_sent=None,
                current_bandwidth_received=None,
                max_packet_size=None,
                lc_perf_other_end_recovery=None,
            ),
            ecc=MetricEccTotals(
                total_correctable_count=None,
                total_uncorrectable_count=None,
                total_deferred_count=None,
                cache_correctable_count=None,
                cache_uncorrectable_count=None,
            ),
            ecc_blocks={},
            fan=MetricFan(speed=None, max=None, rpm=None, usage=None),
            voltage_curve=self._empty_voltage_curve(),
            perf_level=None,
            xgmi_err=None,
            energy=None,
            mem_usage=MetricMemUsage(
                total_vram=None,
                used_vram=None,
                free_vram=None,
                total_visible_vram=None,
                used_visible_vram=None,
                free_visible_vram=None,
                total_gtt=None,
                used_gtt=None,
                free_gtt=None,
            ),
            throttle=MetricThrottle(),
        )

    def _get_voltage_curve(self, h: Any) -> MetricVoltageCurve:
        """Get GPU voltage curve (frequency/voltage points) for overdrive settings.

        Args:
            h (Any): GPU device handle

        Returns:
            MetricVoltageCurve: Voltage curve data with up to 3 frequency/voltage points
        """
        amdsmi = self._amdsmi_mod()
        raw = self._smi_try(amdsmi.amdsmi_get_gpu_od_volt_info, h, default=None)
        if not isinstance(raw, dict):
            return self._empty_voltage_curve()

        try:
            num_regions = int(raw.get("num_regions", 0) or 0)
        except Exception:
            num_regions = 0
        if num_regions == 0:
            return self._empty_voltage_curve()

        curve = raw.get("curve") or {}
        pts = curve.get("vc_points") or raw.get("vc_points") or []
        if not isinstance(pts, list) or len(pts) == 0:
            return self._empty_voltage_curve()

        def _pt_get(d: object, *names: str) -> Optional[object]:
            if not isinstance(d, dict):
                return None
            for n in names:
                if n in d:
                    return d.get(n)
            lower = {str(k).lower(): v for k, v in d.items()}
            for n in names:
                v = lower.get(n.lower())
                if v is not None:
                    return v
            return None

        def _extract_point(p: object) -> tuple[Optional[object], Optional[object]]:
            clk = _pt_get(p, "clk_value", "frequency", "freq", "clk", "sclk")
            volt = _pt_get(p, "volt_value", "voltage", "volt", "mV")
            return clk, volt

        p0_clk, p0_volt = _extract_point(pts[0]) if len(pts) >= 1 else (None, None)
        p1_clk, p1_volt = _extract_point(pts[1]) if len(pts) >= 2 else (None, None)
        p2_clk, p2_volt = _extract_point(pts[2]) if len(pts) >= 3 else (None, None)

        return MetricVoltageCurve(
            point_0_frequency=self._valueunit(p0_clk, "MHz"),
            point_0_voltage=self._valueunit(p0_volt, "mV"),
            point_1_frequency=self._valueunit(p1_clk, "MHz"),
            point_1_voltage=self._valueunit(p1_volt, "mV"),
            point_2_frequency=self._valueunit(p2_clk, "MHz"),
            point_2_voltage=self._valueunit(p2_volt, "mV"),
        )

    def _empty_voltage_curve(self) -> MetricVoltageCurve:
        """Create an empty MetricVoltageCurve with all points set to None.

        Returns:
            MetricVoltageCurve: Empty voltage curve instance
        """
        return MetricVoltageCurve(
            point_0_frequency=None,
            point_0_voltage=None,
            point_1_frequency=None,
            point_1_voltage=None,
            point_2_frequency=None,
            point_2_voltage=None,
        )

    def _as_first_plane(self, obj: object) -> list:
        """Take a scalar/list/2D-list and return the first plane as a flat list.

        Args:
            obj (object): Scalar, list, or 2D-list to process

        Returns:
            list: First plane as a flat list, or empty list if not a list
        """
        if isinstance(obj, list):
            if obj and isinstance(obj[0], list):  # 2D
                return obj[0]
            return obj
        return []

    def _th_vu_list_pct(self, obj: object) -> Optional[MetricThrottleVu]:
        """Return MetricThrottleVu with percentage ValueUnits for the first XCP plane.

        Args:
            obj (object): Object containing throttle data (scalar, list, or 2D-list)

        Returns:
            Optional[MetricThrottleVu]: MetricThrottleVu with percentage values or None
        """
        arr = self._as_first_plane(obj)
        if not arr:
            return None
        return MetricThrottleVu(
            xcp_0=[self._valueunit(v, "%") if v not in (None, "N/A") else "N/A" for v in arr]
        )

    def _th_vu_list_raw(self, obj: object) -> Optional[MetricThrottleVu]:
        """Return MetricThrottleVu with raw integers/strings for the first XCP plane.

        Args:
            obj (object): Object containing throttle data (scalar, list, or 2D-list)

        Returns:
            Optional[MetricThrottleVu]: MetricThrottleVu with raw values or None
        """
        arr = self._as_first_plane(obj)
        if not arr:
            return None
        return MetricThrottleVu(
            xcp_0=[
                (
                    str(int(v))
                    if isinstance(v, (int, float, str)) and str(v).strip().isdigit()
                    else str(v) if v not in (None, "N/A") else None
                )
                for v in arr
            ]
        )

    def get_throttle(self, h: Any) -> MetricThrottle:
        """Get throttle/violation status data for a GPU device.

        Args:
            h (Any): GPU device handle

        Returns:
            MetricThrottle: Throttle metrics and violation status data
        """
        amdsmi = self._amdsmi_mod()
        raw = self._smi_try(amdsmi.amdsmi_get_violation_status, h, default=None)
        if not isinstance(raw, dict):
            return MetricThrottle()

        acc_counter = raw.get("acc_counter")
        prochot_acc = raw.get("acc_prochot_thrm")
        ppt_acc = raw.get("acc_ppt_pwr")
        socket_thrm_acc = raw.get("acc_socket_thrm")
        vr_thrm_acc = raw.get("acc_vr_thrm")
        hbm_thrm_acc = raw.get("acc_hbm_thrm")

        acc_gfx_pwr = raw.get("acc_gfx_clk_below_host_limit_pwr")
        acc_gfx_thm = raw.get("acc_gfx_clk_below_host_limit_thm")
        acc_low_util = raw.get("acc_low_utilization")
        acc_gfx_total = raw.get("acc_gfx_clk_below_host_limit_total")

        act_prochot = raw.get("active_prochot_thrm")
        act_ppt = raw.get("active_ppt_pwr")
        act_socket = raw.get("active_socket_thrm")
        act_vr = raw.get("active_vr_thrm")
        act_hbm = raw.get("active_hbm_thrm")
        act_gfx_pwr = raw.get("active_gfx_clk_below_host_limit_pwr")
        act_gfx_thm = raw.get("active_gfx_clk_below_host_limit_thm")
        act_low_util = raw.get("active_low_utilization")
        act_gfx_total = raw.get("active_gfx_clk_below_host_limit_total")

        per_prochot = raw.get("per_prochot_thrm")
        per_ppt = raw.get("per_ppt_pwr")
        per_socket = raw.get("per_socket_thrm")
        per_vr = raw.get("per_vr_thrm")
        per_hbm = raw.get("per_hbm_thrm")
        per_gfx_pwr = raw.get("per_gfx_clk_below_host_limit_pwr")
        per_gfx_thm = raw.get("per_gfx_clk_below_host_limit_thm")
        per_low_util = raw.get("per_low_utilization")
        per_gfx_total = raw.get("per_gfx_clk_below_host_limit_total")

        return MetricThrottle(
            accumulation_counter=self._valueunit(acc_counter, ""),  # unitless counter
            prochot_accumulated=self._th_vu_list_raw(prochot_acc),
            ppt_accumulated=self._th_vu_list_raw(ppt_acc),
            socket_thermal_accumulated=self._th_vu_list_raw(socket_thrm_acc),
            vr_thermal_accumulated=self._th_vu_list_raw(vr_thrm_acc),
            hbm_thermal_accumulated=self._th_vu_list_raw(hbm_thrm_acc),
            gfx_clk_below_host_limit_power_accumulated=self._th_vu_list_raw(acc_gfx_pwr),
            gfx_clk_below_host_limit_thermal_accumulated=self._th_vu_list_raw(acc_gfx_thm),
            low_utilization_accumulated=self._th_vu_list_raw(acc_low_util),
            total_gfx_clk_below_host_limit_accumulated=self._th_vu_list_raw(acc_gfx_total),
            prochot_violation_status=self._th_vu_list_raw(act_prochot),
            ppt_violation_status=self._th_vu_list_raw(act_ppt),
            socket_thermal_violation_status=self._th_vu_list_raw(act_socket),
            vr_thermal_violation_status=self._th_vu_list_raw(act_vr),
            hbm_thermal_violation_status=self._th_vu_list_raw(act_hbm),
            gfx_clk_below_host_limit_power_violation_status=self._th_vu_list_raw(act_gfx_pwr),
            gfx_clk_below_host_limit_thermal_violation_status=self._th_vu_list_raw(act_gfx_thm),
            low_utilization_violation_status=self._th_vu_list_raw(act_low_util),
            total_gfx_clk_below_host_limit_violation_status=self._th_vu_list_raw(act_gfx_total),
            prochot_violation_activity=self._valueunit(per_prochot, "%"),
            ppt_violation_activity=self._valueunit(per_ppt, "%"),
            socket_thermal_violation_activity=self._valueunit(per_socket, "%"),
            vr_thermal_violation_activity=self._valueunit(per_vr, "%"),
            hbm_thermal_violation_activity=self._valueunit(per_hbm, "%"),
            gfx_clk_below_host_limit_power_violation_activity=self._th_vu_list_pct(per_gfx_pwr),
            gfx_clk_below_host_limit_thermal_violation_activity=self._th_vu_list_pct(per_gfx_thm),
            low_utilization_violation_activity=self._th_vu_list_pct(per_low_util),
            total_gfx_clk_below_host_limit_violation_activity=self._th_vu_list_pct(per_gfx_total),
        )

    def _flatten_2d(self, v: object) -> list[object]:
        """Flatten a 2D list into a 1D list, or normalize scalars/None to lists.

        Args:
            v (object): Input value (scalar, list, or 2D-list)

        Returns:
            list[object]: Flattened list of objects
        """
        if isinstance(v, list) and v and isinstance(v[0], list):
            out: list[object] = []
            for row in v:
                if isinstance(row, list):
                    out.extend(row)
                else:
                    out.append(row)
            return out
        return v if isinstance(v, list) else [v] if v not in (None, "N/A") else []

    def _coerce_throttle_value(
        self, v: object, unit: str = ""
    ) -> Optional[Union[MetricThrottleVu, ValueUnit]]:
        """Convert various throttle data formats to ValueUnit or MetricThrottleVu.

        Converts integers/floats/strings/lists/2D-lists/dicts into appropriate types:
          - ValueUnit for scalar values
          - MetricThrottleVu(xcp_0=[...]) for lists/arrays
          - None for N/A or empty values

        Args:
            v (object): Input throttle value in various formats
            unit (str, optional): Unit of measurement. Defaults to empty string.

        Returns:
            Optional[Union[MetricThrottleVu, ValueUnit]]: Coerced throttle value or None
        """
        if v in (None, "", "N/A"):
            return None

        if isinstance(v, (int, float)):
            return ValueUnit(value=v, unit=unit)
        if isinstance(v, str):
            s = v.strip()
            if not s or s.upper() == "N/A":
                return None
            try:
                return ValueUnit(value=int(s, 0), unit=unit)
            except Exception:
                try:
                    return ValueUnit(value=float(s), unit=unit)
                except Exception:
                    return MetricThrottleVu(xcp_0=[s])

        if isinstance(v, list):
            flat = self._flatten_2d(v)
            return MetricThrottleVu(
                xcp_0=cast(Optional[list[Optional[Union[ValueUnit, str]]]], flat if flat else None)
            )

        if isinstance(v, dict):
            if "xcp_0" in v and isinstance(v["xcp_0"], list):
                return MetricThrottleVu(
                    xcp_0=cast(
                        Optional[list[Optional[Union[ValueUnit, str]]]],
                        self._flatten_2d(v["xcp_0"]),
                    )
                )
            val = v.get("value")
            if isinstance(val, dict):
                for maybe_list in val.values():
                    if isinstance(maybe_list, list):
                        return MetricThrottleVu(
                            xcp_0=cast(
                                Optional[list[Optional[Union[ValueUnit, str]]]],
                                self._flatten_2d(maybe_list),
                            )
                        )
            return MetricThrottleVu(xcp_0=[str(v)])

        return MetricThrottleVu(xcp_0=[str(v)])

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
