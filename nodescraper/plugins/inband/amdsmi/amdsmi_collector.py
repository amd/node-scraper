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
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from nodescraper.base.inbandcollectortask import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.models.datamodel import FileModel
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiListItem,
    AmdSmiStatic,
    AmdSmiVersion,
    EccState,
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
    StaticRas,
    StaticSocPstate,
    StaticVbios,
    StaticVram,
    StaticXgmiPlpd,
    ValueUnit,
)
from nodescraper.plugins.inband.amdsmi.collector_args import AmdSmiCollectorArgs
from nodescraper.utils import get_exception_traceback


class AmdSmiCollector(InBandDataCollector[AmdSmiDataModel, AmdSmiCollectorArgs]):
    """Class for collection of inband tool amd-smi data."""

    AMD_SMI_EXE = "amd-smi"

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = AmdSmiDataModel

    CMD_VERSION = "version --json"
    CMD_LIST = "list --json"
    CMD_PROCESS = "process --json"
    CMD_PARTITION = "partition --json"
    CMD_FIRMWARE = "firmware --json"
    CMD_STATIC = "static -g all --json"
    CMD_STATIC_GPU = "static -g {gpu_id} --json"
    CMD_RAS = "ras --cper --folder={folder}"
    CMD_RAS_AFID = "ras --afid --cper-file {cper_file}"

    def _check_amdsmi_installed(self) -> bool:
        """Check if amd-smi is installed

        Returns:
            bool: True if amd-smi is installed, False otherwise
        """
        cmd_ret = self._run_sut_cmd("which amd-smi")
        return bool(cmd_ret.exit_code == 0 and "no amd-smi in" not in cmd_ret.stdout)

    def _run_amd_smi(self, cmd: str) -> Optional[str]:
        """Run amd-smi command

        Args:
            cmd (str): command arguments to pass to amd-smi

        Returns:
            Optional[str]: stdout from command or None on error
        """
        cmd_ret = self._run_sut_cmd(f"{self.AMD_SMI_EXE} {cmd}")

        # Check for known warnings and errors that can be handled
        is_group_warning = (
            "User is missing the following required groups" in cmd_ret.stderr
            or "User is missing the following required groups" in cmd_ret.stdout
        )

        # Check for known amd-smi internal errors
        is_amdsmi_internal_error = any(
            pattern in cmd_ret.stderr for pattern in ["KeyError:", "AttributeError:", "IndexError:"]
        )

        # Log warning if user is missing group
        if cmd_ret.stderr != "" or cmd_ret.exit_code != 0:
            if is_amdsmi_internal_error:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="amd-smi internal error detected",
                    data={
                        "command": cmd,
                        "exit_code": cmd_ret.exit_code,
                        "stderr": cmd_ret.stderr,
                    },
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                return None
            elif not is_group_warning:
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
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="amd-smi warning (continuing): User missing required groups",
                    data={
                        "command": cmd,
                        "warning": cmd_ret.stderr or cmd_ret.stdout,
                    },
                    priority=EventPriority.WARNING,
                    console_log=False,
                )

        stdout = cmd_ret.stdout
        if is_group_warning and stdout:
            lines = stdout.split("\n")
            cleaned_lines = [
                line
                for line in lines
                if not any(
                    warn in line
                    for warn in [
                        "RuntimeError:",
                        "WARNING: User is missing",
                        "Please add user to these groups",
                    ]
                )
            ]
            stdout = "\n".join(cleaned_lines).strip()

        return stdout

    def _run_amd_smi_dict(self, cmd: str) -> Optional[Union[dict, list[dict]]]:
        """Run amd-smi command with json output

        Args:
            cmd (str): command arguments to pass to amd-smi

        Returns:
            Optional[Union[dict, list[dict]]]: parsed JSON output or None on error
        """
        cmd += " --json"
        cmd_ret = self._run_amd_smi(cmd)
        if cmd_ret:
            try:
                # Try to parse as single JSON first
                return json.loads(cmd_ret)
            except json.JSONDecodeError as e:
                # try to extract and parse multiple JSON objects
                try:
                    json_objects = []
                    decoder = json.JSONDecoder()
                    idx = 0
                    cmd_ret_stripped = cmd_ret.strip()

                    while idx < len(cmd_ret_stripped):
                        while idx < len(cmd_ret_stripped) and cmd_ret_stripped[idx].isspace():
                            idx += 1

                        if idx >= len(cmd_ret_stripped):
                            break

                        if cmd_ret_stripped[idx] not in ["{", "["]:
                            break

                        try:
                            obj, end_idx = decoder.raw_decode(cmd_ret_stripped, idx)
                            json_objects.append(obj)
                            idx = end_idx
                        except json.JSONDecodeError:
                            break

                    if json_objects:
                        return json_objects if len(json_objects) > 1 else json_objects[0]
                    else:
                        raise

                except Exception:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description=f"Error parsing command: `{cmd}` json data",
                        data={
                            "cmd": cmd,
                            "exception": get_exception_traceback(e),
                        },
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )
                    return None
        return None

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
            cper_data, cper_afids = self.get_cper_data()
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
                cper_data=cper_data,
                cper_afids=cper_afids,
            )
        except ValidationError as err:
            self.logger.warning("Validation err: %s", err)
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiDataModel",
                data={"errors": err.errors(include_url=False)},
                priority=EventPriority.ERROR,
            )
            return None

    def _get_amdsmi_version(self) -> Optional[AmdSmiVersion]:
        """Get amdsmi version and data

        Returns:
            Optional[AmdSmiVersion]: version information or None on error
        """
        ret = self._run_amd_smi_dict(self.CMD_VERSION)
        if not ret or not isinstance(ret, list) or len(ret) == 0:
            return None

        version_data = ret[0] if isinstance(ret, list) else ret
        if not isinstance(version_data, dict):
            return None

        try:
            return AmdSmiVersion(
                tool="amdsmi",
                version=version_data.get("amdsmi_library_version", ""),
                amdsmi_library_version=version_data.get("amdsmi_library_version", ""),
                rocm_version=version_data.get("rocm_version", ""),
            )
        except ValidationError as err:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiVersion",
                data={"errors": err.errors(include_url=False)},
                priority=EventPriority.WARNING,
            )
            return None

    def get_gpu_list(self) -> Optional[list[AmdSmiListItem]]:
        """Get GPU information from amd-smi list command

        Returns:
            Optional[list[AmdSmiListItem]]: list of GPU info items
        """
        ret = self._run_amd_smi_dict(self.CMD_LIST)
        if not ret:
            return []

        gpu_data = ret if isinstance(ret, list) else [ret]
        out: list[AmdSmiListItem] = []

        def _to_int(x: Any, default: int = 0) -> int:
            try:
                return int(x)
            except Exception:
                return default

        for item in gpu_data:
            if not isinstance(item, dict):
                continue

            try:
                out.append(
                    AmdSmiListItem(
                        gpu=_to_int(item.get("gpu", 0)),
                        bdf=str(item.get("bdf", "")),
                        uuid=str(item.get("uuid", "")),
                        kfd_id=_to_int(item.get("kfd_id", 0)),
                        node_id=_to_int(item.get("node_id", 0)),
                        partition_id=_to_int(item.get("partition_id", 0)),
                    )
                )
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiListItem",
                    data={"errors": err.errors(include_url=False), "item": item},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_process(self) -> Optional[list[Processes]]:
        """Get process information

        Returns:
            Optional[list[Processes]]: list of GPU processes
        """
        ret = self._run_amd_smi_dict(self.CMD_PROCESS)
        if not ret:
            return []

        process_data = ret if isinstance(ret, list) else [ret]
        out: list[Processes] = []

        for item in process_data:
            if not isinstance(item, dict):
                continue

            gpu_idx = int(item.get("gpu", 0)) if item.get("gpu") not in (None, "") else 0
            process_list_raw = item.get("process_list", [])
            if not isinstance(process_list_raw, list):
                continue

            plist: list[ProcessListItem] = []

            for entry in process_list_raw:
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

                try:
                    plist.append(
                        ProcessListItem(
                            process_info=ProcessInfo(
                                name=str(name),
                                pid=pid,
                                memory_usage=mem_usage,
                                mem_usage=mem_vu,
                                usage=usage,
                            )
                        )
                    )
                except ValidationError as err:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="Failed to build ProcessListItem; skipping entry",
                        data={
                            "errors": err.errors(include_url=False),
                            "gpu_index": gpu_idx,
                            "entry": repr(entry),
                        },
                        priority=EventPriority.WARNING,
                    )
                    continue

            try:
                out.append(Processes(gpu=gpu_idx, process_list=plist))
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build Processes",
                    data={"errors": err.errors(include_url=False), "gpu_index": gpu_idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_partition(self) -> Optional[Partition]:
        """Check partition information

        Returns:
            Optional[Partition]: Partition data if available
        """
        ret = self._run_amd_smi_dict(self.CMD_PARTITION)
        if not ret:
            return None

        partition_data = ret if isinstance(ret, list) else [ret]
        memparts: list[PartitionMemory] = []
        computeparts: list[PartitionCompute] = []

        # Flatten multi-JSON results (partition command returns multiple JSON arrays)
        flattened_data = []
        for item in partition_data:
            if isinstance(item, list):
                flattened_data.extend(item)
            elif isinstance(item, dict):
                flattened_data.append(item)

        for item in flattened_data:
            if not isinstance(item, dict):
                continue

            gpu_idx = int(item.get("gpu", 0)) if item.get("gpu") not in (None, "") else 0
            mem_pt = item.get("memory_partition")
            comp_pt = item.get("compute_partition")

            try:
                memparts.append(
                    PartitionMemory(gpu_id=gpu_idx, partition_type=str(mem_pt) if mem_pt else None)
                )
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionMemory",
                    data={
                        "errors": err.errors(include_url=False),
                        "gpu_index": gpu_idx,
                        "data": mem_pt,
                    },
                    priority=EventPriority.WARNING,
                )

            try:
                computeparts.append(
                    PartitionCompute(
                        gpu_id=gpu_idx, partition_type=str(comp_pt) if comp_pt else None
                    )
                )
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build PartitionCompute",
                    data={
                        "errors": err.errors(include_url=False),
                        "gpu_index": gpu_idx,
                        "data": comp_pt,
                    },
                    priority=EventPriority.WARNING,
                )

        try:
            return Partition(memory_partition=memparts, compute_partition=computeparts)
        except ValidationError as err:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build Partition",
                data={"errors": err.errors(include_url=False)},
                priority=EventPriority.WARNING,
            )
            return None

    def get_firmware(self) -> Optional[list[Fw]]:
        """Get firmware information

        Returns:
            Optional[list[Fw]]: List of firmware info per GPU
        """
        ret = self._run_amd_smi_dict(self.CMD_FIRMWARE)
        if not ret:
            return []

        firmware_data = ret if isinstance(ret, list) else [ret]
        out: list[Fw] = []

        for item in firmware_data:
            if not isinstance(item, dict):
                continue

            gpu_idx = int(item.get("gpu", 0)) if item.get("gpu") not in (None, "") else 0
            fw_list_raw = item.get("fw_list", [])

            if not isinstance(fw_list_raw, list):
                continue

            normalized: list[FwListItem] = []
            for e in fw_list_raw:
                if isinstance(e, dict):
                    fid = e.get("fw_name")
                    ver = e.get("fw_version")
                    normalized.append(
                        FwListItem(
                            fw_id="" if fid is None else str(fid),
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
                out.append(Fw(gpu=gpu_idx, fw_list=normalized))
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build Fw",
                    data={"errors": err.errors(include_url=False), "gpu_index": gpu_idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def get_static(self) -> Optional[list[AmdSmiStatic]]:
        """Get Static info from amd-smi static command

        Returns:
            Optional[list[AmdSmiStatic]]: list of AmdSmiStatic instances or empty list
        """
        ret = self._run_amd_smi_dict(self.CMD_STATIC)
        if not ret:
            self.logger.info("Bulk static query failed, attempting per-GPU fallback")
            gpu_list = self.get_gpu_list()
            if gpu_list:
                fallback_data: list[dict] = []
                for gpu in gpu_list:
                    gpu_data = self._run_amd_smi_dict(self.CMD_STATIC_GPU.format(gpu_id=gpu.gpu))
                    if gpu_data:
                        if isinstance(gpu_data, dict):
                            fallback_data.append(gpu_data)
                        elif isinstance(gpu_data, list):
                            fallback_data.extend(gpu_data)
                if fallback_data:
                    ret = fallback_data
                else:
                    return []
            else:
                return []

        if isinstance(ret, dict) and "gpu_data" in ret:
            ret = ret["gpu_data"]

        static_data = ret if isinstance(ret, list) else [ret]
        out: list[AmdSmiStatic] = []

        for item in static_data:
            if not isinstance(item, dict) or "gpu" not in item:
                continue

            gpu_idx = int(item.get("gpu", 0)) if item.get("gpu") not in (None, "") else 0

            asic = item.get("asic", {}) or {}
            board = item.get("board", {}) or {}
            bus = item.get("bus", {}) or {}
            vbios = item.get("vbios", {}) or {}
            driver = item.get("driver", {}) or {}
            numa = item.get("numa", {}) or {}
            vram = item.get("vram", {}) or {}
            ras = item.get("ras", {}) or {}
            cache = item.get("cache", {}) or {}
            clock = item.get("clock", {}) or {}
            soc_pstate = item.get("soc_pstate", {}) or {}
            xgmi_plpd = item.get("xgmi_plpd", {}) or {}

            # Bus / PCIe
            bus_model = StaticBus(
                bdf=str(bus.get("bdf", "")),
                max_pcie_width=self._valueunit(bus.get("max_pcie_width"), "x"),
                max_pcie_speed=self._valueunit(bus.get("max_pcie_speed"), "GT/s"),
                pcie_interface_version=self._normalize(bus.get("pcie_interface_version")),
                slot_type=self._normalize(bus.get("slot_type"), slot_type=True),
            )

            # ASIC
            oam_id_raw = asic.get("oam_id")
            if oam_id_raw in (None, "", "N/A"):
                oam_id_val: Union[int, str] = "N/A"
            elif isinstance(oam_id_raw, str):
                oam_id_val = oam_id_raw
            else:
                oam_id_val = int(oam_id_raw) if oam_id_raw is not None else "N/A"

            num_cu_raw = asic.get("num_compute_units")
            if num_cu_raw in (None, "", "N/A"):
                num_cu_val: Union[int, str] = "N/A"
            elif isinstance(num_cu_raw, str):
                num_cu_val = num_cu_raw
            else:
                num_cu_val = int(num_cu_raw) if num_cu_raw is not None else "N/A"

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
                oam_id=oam_id_val,
                num_compute_units=num_cu_val,
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
            driver_model = StaticDriver(
                name=self._normalize(
                    driver.get("driver_name") if driver else None, default="unknown"
                ),
                version=self._normalize(
                    driver.get("driver_version") if driver else None, default="unknown"
                ),
            )

            # VBIOS
            vbios_model: Optional[StaticVbios] = None
            if vbios:
                vbios_model = StaticVbios(
                    name=str(vbios.get("vbios_name", "")),
                    build_date=str(vbios.get("vbios_build_date", "")),
                    part_number=str(vbios.get("vbios_part_number", "")),
                    version=str(vbios.get("vbios_version", "")),
                )

            # NUMA
            numa_node = int(numa.get("node", 0) or 0)
            affinity_raw = numa.get("affinity")
            if affinity_raw in (None, "", "N/A"):
                affinity_val: Union[int, str] = "N/A"
            elif isinstance(affinity_raw, str):
                affinity_val = affinity_raw
            else:
                affinity_val = int(affinity_raw) if affinity_raw is not None else "N/A"

            numa_model = StaticNuma(node=numa_node, affinity=affinity_val)

            # VRAM
            vram_type = str(vram.get("vram_type", "") or "unknown")
            vram_vendor = vram.get("vram_vendor")
            vram_bits = vram.get("vram_bit_width")
            vram_size_b: Optional[int] = None
            if vram.get("vram_size_mb") is not None:
                try:
                    vram_size_b = int(vram["vram_size_mb"]) * 1024 * 1024
                except Exception:
                    vram_size_b = None

            vram_model = StaticVram(
                type=vram_type,
                vendor=None if vram_vendor in (None, "", "N/A") else str(vram_vendor),
                size=self._valueunit(vram_size_b, "B"),
                bit_width=self._valueunit(vram_bits, "bit"),
                max_bandwidth=None,
            )

            # SOC P-state
            soc_pstate_model = self._parse_soc_pstate(soc_pstate)

            # XGMI PLPD
            xgmi_plpd_model = self._parse_xgmi_plpd(xgmi_plpd)

            # RAS
            ras_model = self._parse_ras(ras)

            # Cache info
            cache_info_model = self._parse_cache_info(cache)

            # Clock
            clock_dict_model = self._parse_clock_dict(clock)

            try:
                out.append(
                    AmdSmiStatic(
                        gpu=gpu_idx,
                        asic=asic_model,
                        bus=bus_model,
                        vbios=vbios_model,
                        limit=None,
                        driver=driver_model,
                        board=board_model,
                        ras=ras_model,
                        soc_pstate=soc_pstate_model,
                        xgmi_plpd=xgmi_plpd_model,
                        process_isolation="",
                        numa=numa_model,
                        vram=vram_model,
                        cache_info=cache_info_model,
                        partition=None,
                        clock=clock_dict_model,
                    )
                )
            except ValidationError as err:
                self.logger.error(err)
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Failed to build AmdSmiStatic",
                    data={"errors": err.errors(include_url=False), "gpu_index": gpu_idx},
                    priority=EventPriority.WARNING,
                )

        return out

    def _parse_soc_pstate(self, data: dict) -> Optional[StaticSocPstate]:
        """Parse SOC P-state data

        Args:
            data (dict): SOC P-state data from amd-smi

        Returns:
            Optional[StaticSocPstate]: StaticSocPstate instance or None
        """
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

    def _parse_xgmi_plpd(self, data: dict) -> Optional[StaticXgmiPlpd]:
        """Parse XGMI PLPD data

        Args:
            data (dict): XGMI PLPD data from amd-smi

        Returns:
            Optional[StaticXgmiPlpd]: StaticXgmiPlpd instance or None
        """
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

    def _parse_ras(self, data: dict) -> StaticRas:
        """Parse RAS/ECC data

        Args:
            data (dict): RAS data from amd-smi

        Returns:
            StaticRas: StaticRas instance with default values if data is missing
        """
        if not isinstance(data, dict):
            # Return default RAS data
            return StaticRas(
                eeprom_version="N/A",
                parity_schema=EccState.NA,
                single_bit_schema=EccState.NA,
                double_bit_schema=EccState.NA,
                poison_schema=EccState.NA,
                ecc_block_state={},
            )

        def _to_ecc_state(value: Any) -> EccState:
            """Convert string to EccState enum"""
            if not value or not isinstance(value, str):
                return EccState.NA
            try:
                return EccState(value.upper())
            except (ValueError, AttributeError):
                return EccState.NA

        eeprom_version = str(data.get("eeprom_version", "N/A") or "N/A")
        parity_schema = _to_ecc_state(data.get("parity_schema"))
        single_bit_schema = _to_ecc_state(data.get("single_bit_schema"))
        double_bit_schema = _to_ecc_state(data.get("double_bit_schema"))
        poison_schema = _to_ecc_state(data.get("poison_schema"))

        ecc_block_state = data.get("ecc_block_state", {})
        ecc_block_state_final: Union[Dict[str, EccState], str]
        if isinstance(ecc_block_state, dict):
            parsed_blocks = {}
            for block_name, block_state in ecc_block_state.items():
                parsed_blocks[block_name] = _to_ecc_state(block_state)
            ecc_block_state_final = parsed_blocks
        elif isinstance(ecc_block_state, str):
            ecc_block_state_final = ecc_block_state
        else:
            ecc_block_state_final = {}

        try:
            return StaticRas(
                eeprom_version=eeprom_version,
                parity_schema=parity_schema,
                single_bit_schema=single_bit_schema,
                double_bit_schema=double_bit_schema,
                poison_schema=poison_schema,
                ecc_block_state=ecc_block_state_final,
            )
        except ValidationError:
            # Return default if validation fails
            return StaticRas(
                eeprom_version="N/A",
                parity_schema=EccState.NA,
                single_bit_schema=EccState.NA,
                double_bit_schema=EccState.NA,
                poison_schema=EccState.NA,
                ecc_block_state={},
            )

    def _parse_cache_info(self, data: dict) -> list[StaticCacheInfoItem]:
        """Parse cache info data

        Args:
            data (dict): Cache data from amd-smi

        Returns:
            list[StaticCacheInfoItem]: list of StaticCacheInfoItem instances
        """
        if not isinstance(data, dict) or not isinstance(data.get("cache"), list):
            return []

        items = data["cache"]

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
            except ValidationError as err:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description="Bad cache info entry from amd-smi; skipping",
                    data={"entry": repr(e), "errors": err.errors(include_url=False)},
                    priority=EventPriority.WARNING,
                )
                continue

        return out

    def _parse_clock(self, data: dict) -> Optional[StaticClockData]:
        """Parse clock data

        Args:
            data (dict): Clock data from amd-smi

        Returns:
            Optional[StaticClockData]: StaticClockData instance or None
        """
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

            # Use the alias "current level" as defined in the model
            return StaticClockData.model_validate(
                {"frequency_levels": levels, "current level": current}
            )
        except ValidationError:
            return None

    def _parse_clock_dict(self, data: dict) -> Optional[dict[str, Union[StaticClockData, None]]]:
        """Parse clock data into dictionary structure

        Args:
            data (dict): Clock data from amd-smi

        Returns:
            Optional[dict[str, Union[StaticClockData, None]]]: dictionary of clock data or None
        """
        if not isinstance(data, dict):
            return None

        clock_dict: dict[str, Union[StaticClockData, None]] = {}

        clock_data = self._parse_clock(data)
        if clock_data:
            clock_dict["clk"] = clock_data

        return clock_dict if clock_dict else None

    def get_cper_data(self) -> tuple[List[FileModel], Dict[str, int]]:
        """Collect CPER data from amd-smi ras command and extract AFID for each file

        Returns:
            tuple[list[FileModel], dict[str, int]]: Tuple of (list of CPER files, dict mapping filenames to AFIDs)
                                                     Returns empty list and dict if not supported/available
        """
        try:
            AMD_SMI_CPER_FOLDER = "/tmp/amd_smi_cper"
            # Ensure the cper folder exists but is empty
            self._run_sut_cmd(
                f"mkdir -p {AMD_SMI_CPER_FOLDER} && rm -f {AMD_SMI_CPER_FOLDER}/*.cper && rm -f {AMD_SMI_CPER_FOLDER}/*.json",
                sudo=False,
            )
            # Run amd-smi ras command with sudo to collect CPER data
            cper_cmd_ret = self._run_sut_cmd(
                f"{self.AMD_SMI_EXE} {self.CMD_RAS.format(folder=AMD_SMI_CPER_FOLDER)}",
                sudo=True,
            )
            if cper_cmd_ret.exit_code != 0:
                # Command failed, return empty list and dict
                return [], {}
            cper_cmd = cper_cmd_ret.stdout
            # search that a CPER is actually created here
            regex_cper_search = re.findall(r"(\w+\.cper)", cper_cmd)
            if not regex_cper_search:
                # Early exit if no CPER files were created
                return [], {}
            # tar the cper folder
            self._run_sut_cmd(
                f"tar -czf {AMD_SMI_CPER_FOLDER}.tar.gz -C {AMD_SMI_CPER_FOLDER} .",
                sudo=True,
            )
            # Load the tar files
            cper_zip = self._read_sut_file(
                f"{AMD_SMI_CPER_FOLDER}.tar.gz", encoding=None, strip=False, log_artifact=True
            )
            # Since encoding=None, this returns BinaryFileArtifact which has contents: bytes
            if hasattr(cper_zip, "contents"):
                io_bytes = io.BytesIO(cper_zip.contents)  # type: ignore[attr-defined]
            else:
                return [], {}
            del cper_zip  # Free memory after reading the file
            try:
                with TarFile.open(fileobj=io_bytes, mode="r:gz") as tar_file:
                    cper_data = []
                    cper_afids = {}
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

                            cper_file_path = f"{AMD_SMI_CPER_FOLDER}/{member.name}"
                            afid = self._get_cper_afid(cper_file_path)
                            if afid is not None:
                                cper_afids[member.name] = afid

                # Since we do not log the cper data in the data model create an event informing the user if CPER created
                if cper_data:
                    self._log_event(
                        category=EventCategory.APPLICATION,
                        description="CPER data has been extracted from amd-smi",
                        data={
                            "cper_count": len(cper_data),
                            "afid_count": len(cper_afids),
                        },
                        priority=EventPriority.INFO,
                        console_log=True,
                    )
                return cper_data, cper_afids
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
                return [], {}
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error collecting CPER data",
                data={
                    "exception": get_exception_traceback(e),
                },
                priority=EventPriority.WARNING,
                console_log=False,
            )
            return [], {}

    def _get_cper_afid(self, cper_file_path: str) -> Optional[int]:
        """Get AFID from a CPER file using amd-smi ras --afid --cper-file command

        Args:
            cper_file_path (str): Path to the CPER file

        Returns:
            Optional[int]: AFID value or None if command fails or no value found
        """
        cmd = self.CMD_RAS_AFID.format(cper_file=cper_file_path)
        result = self._run_amd_smi(cmd)

        if result is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Failed to get AFID from CPER file: {cper_file_path}",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None

        try:
            afid = int(result.strip())
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Successfully retrieved AFID from CPER file: {cper_file_path}",
                data={"afid": afid, "cper_file": cper_file_path},
                priority=EventPriority.INFO,
                console_log=True,
            )
            return afid
        except ValueError:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"Failed to parse AFID value from output: {result}",
                data={"output": result, "cper_file": cper_file_path},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None

    def collect_data(
        self,
        args: Optional[AmdSmiCollectorArgs] = None,
    ) -> tuple[TaskResult, Optional[AmdSmiDataModel]]:
        """Collect AmdSmi data from system

        Args:
            args: Optional collector arguments. If cper_file_path is provided,
                  AFID will be extracted and stored in cper_afids dict.

        Returns:
            tuple[TaskResult, Optional[AmdSmiDataModel]]: task result and data model
        """

        if not self._check_amdsmi_installed():
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amd-smi is not installed",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        try:
            version = self._get_amdsmi_version()
            if version is not None:
                self.logger.info("amd-smi version: %s", version.version)
                self.logger.info("ROCm version: %s", version.rocm_version)

            amd_smi_data = self._get_amdsmi_data()

            if amd_smi_data is None:
                return self.result, None

            if args and args.cper_file_path:
                afid = self._get_cper_afid(args.cper_file_path)
                if afid is not None:
                    amd_smi_data.cper_afids[args.cper_file_path] = afid

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
