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
    PartitionCurrent,
    PartitionMemory,
    Processes,
    ProcessInfo,
    ProcessListItem,
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
    """class for collection of inband tool amd-smi data."""

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
                raw_list = (
                    self._smi_try(self._amdsmi.amdsmi_get_gpu_process_list, h, default=[]) or []
                )
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

                    mem_vu = self._vu(entry.get("mem"), "B")
                    mu = entry.get("memory_usage") or {}
                    mem_usage = {
                        "gtt_mem": self._vu(mu.get("gtt_mem"), "B"),
                        "cpu_mem": self._vu(mu.get("cpu_mem"), "B"),
                        "vram_mem": self._vu(mu.get("vram_mem"), "B"),
                    }

                    eu = entry.get("engine_usage") or {}
                    usage = {
                        "gfx": self._vu(eu.get("gfx"), "ns"),
                        "enc": self._vu(eu.get("enc"), "ns"),
                    }

                    cu_occ = self._vu(entry.get("cu_occupancy"), "")

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
        resources: list[dict] = []

        for idx, h in enumerate(devices):
            # compute
            c = self._smi_try(self._amdsmi.amdsmi_get_gpu_compute_partition, h, default={}) or {}
            c_dict = c if isinstance(c, dict) else {}

            # memory
            m = self._smi_try(self._amdsmi.amdsmi_get_gpu_memory_partition, h, default={}) or {}
            m_dict = m if isinstance(m, dict) else {}

            prof_list: list[dict] = (
                []
            )  # amdsmi_get_gpu_accelerator_partition_profile -> currently not supported

            try:
                current.append(
                    PartitionCurrent(
                        gpu_id=idx,
                        memory=c_dict.get("memory"),
                        accelerator_type=c_dict.get("accelerator_type"),
                        accelerator_profile_index=c_dict.get("accelerator_profile_index"),
                        partition_id=c_dict.get("partition_id"),
                    )
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionCurrent",
                    data={
                        "exception": get_exception_traceback(e),
                        "gpu_index": idx,
                        "data": c_dict,
                    },
                    priority=EventPriority.WARNING,
                )

            try:
                memparts.append(
                    PartitionMemory(
                        gpu_id=idx,
                        memory_partition_caps=m_dict.get("memory_partition_caps"),
                        current_partition_id=m_dict.get("current_partition_id"),
                    )
                )
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionMemory",
                    data={
                        "exception": get_exception_traceback(e),
                        "gpu_index": idx,
                        "data": m_dict,
                    },
                    priority=EventPriority.WARNING,
                )

            resources.append({"gpu_id": idx, "profiles": []})

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
                        max_pcie_width=self._vu(max_w, "x"),
                        max_pcie_speed=self._vu(max_s, "GT/s"),
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

            # Driver
            driver_model = None
            drv_fn = getattr(self._amdsmi, "amdsmi_get_gpu_driver_info", None)
            if callable(drv_fn):
                drv = self._smi_try(drv_fn, h, default={}) or {}
                driver_model = StaticDriver(
                    name=_nz(drv.get("driver_name"), default="unknown"),
                    version=_nz(drv.get("driver_version"), default="unknown"),
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
                size=self._vu(vram_size_b, "B"),
                bit_width=self._vu(vram_bits, "bit"),
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
                        limit=None,  # not available via API
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

    def _get_soc_pstate(self, h) -> StaticSocPstate | None:
        fn = getattr(self._amdsmi, "amdsmi_get_soc_pstate", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amdsmi_get_soc_pstate not exposed by amdsmi build",
                priority=EventPriority.INFO,
            )
            return None

        data = self._smi_try(fn, h, default=None)
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

    def _get_xgmi_plpd(self, h) -> StaticXgmiPlpd | None:
        fn = getattr(self._amdsmi, "amdsmi_get_xgmi_plpd", None)
        if not callable(fn):
            self._log_event(
                category=EventCategory.APPLICATION,
                description="XGMI PLPD not exposed by this amdsmi build",
                priority=EventPriority.INFO,
            )
            return None

        data = self._smi_try(fn, h, default=None)
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

    def _get_cache_info(self, h) -> list[StaticCacheInfoItem]:
        """Map amdsmi_get_gpu_cache_info -> List[StaticCacheInfoItem]."""
        raw = self._smi_try(self._amdsmi.amdsmi_get_gpu_cache_info, h, default=None)
        if raw is None:
            return []

        items = raw if isinstance(raw, list) else [raw]

        def _as_list_str(v) -> list[str]:
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

            cache_level = self._vu(e.get("cache_level"), "", required=True)
            max_num_cu_shared = self._vu(e.get("max_num_cu_shared"), "", required=True)
            num_cache_instance = self._vu(e.get("num_cache_instance"), "", required=True)
            cache_size = self._vu(e.get("cache_size"), "", required=False)
            cache_props = _as_list_str(e.get("cache_properties"))

            # AMDSMI doesn’t give a name , "Lable_<level>" as the label???
            cache_label_val = f"Lable_{int(cache_level.value) if isinstance(cache_level.value, (int, float)) else cache_level.value}"
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

    def _get_clock(self, h) -> StaticClockData | None:
        """ """
        fn = getattr(self._amdsmi, "amdsmi_get_clk_freq", None)
        clk_type = getattr(self._amdsmi, "AmdSmiClkType", None)
        if not callable(fn) or clk_type is None or not hasattr(clk_type, "SYS"):
            return None

        data = self._smi_try(fn, h, clk_type.SYS, default=None)
        if not isinstance(data, dict):
            return None

        freqs_raw = data.get("frequency")
        if not isinstance(freqs_raw, list):
            return None

        freqs_mhz: list[int] = []
        for v in freqs_raw:
            if isinstance(v, (int, float)):
                freqs_mhz.append(int(round(float(v) / 1_000_000.0)))

        if not freqs_mhz:
            return None

        def _fmt(n: int | None) -> str | None:
            return None if n is None else f"{n} MHz"

        level0: str = _fmt(freqs_mhz[0]) or "0 MHz"
        level1: str | None = _fmt(freqs_mhz[1]) if len(freqs_mhz) > 1 else None
        level2: str | None = _fmt(freqs_mhz[2]) if len(freqs_mhz) > 2 else None

        cur_raw = data.get("current")
        try:
            current: int | None = None if cur_raw in (None, "", "N/A") else int(cur_raw)
        except Exception:
            current = None

        try:
            levels = StaticFrequencyLevels(Level_0=level0, Level_1=level1, Level_2=level2)
            return StaticClockData(frequency=levels, current=current)
        except ValidationError:
            return None

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

    def _vu(self, v: object, unit: str, *, required: bool = False) -> ValueUnit | None:
        """
        Build ValueUnit from mixed numeric/string input.
        Returns:
             None for None/''/'N/A' unless required=True, in which case ValueUnit(0, unit).
        """
        if v in (None, "", "N/A"):
            return ValueUnit(value=0, unit=unit) if required else None
        try:
            if isinstance(v, str):
                s = v.strip()
                try:
                    n = int(s)
                except Exception:
                    n = float(s)
            elif isinstance(v, (int, float)):
                n = v
            else:
                n = int(v)
        except Exception:
            return ValueUnit(value=0, unit=unit) if required else None
        return ValueUnit(value=n, unit=unit)
