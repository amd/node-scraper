"""amd-smi collector adding mxGPU host-driver (gim/amdgpuv, incl. ESXi) and guest-VF
support on top of the base guest/bare-metal-only AmdSmiCollector.

The amd-smi CLI syntax and JSON schema depend on the loaded driver "flavor":
  - host       - mxGPU host driver (gim on Linux, amdgpuv on ESXi) -> HostDriver* models
  - guest      - amdgpu on a virtual function inside a VM           -> Guest* models
  - bare-metal - amdgpu on physical hardware                        -> base AmdSmi* models
This collector detects the flavor, issues the flavor-appropriate commands, and builds
the matching model variants into AmdSmiFlavorDataModel. The base AmdSmiCollector is
left unchanged for callers that do not need host/VF support.
"""

from __future__ import annotations

import io
import json
import re
from tarfile import TarFile
from typing import Any, Optional, Union

from pydantic import BaseModel, ValidationError

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.models.datamodel import FileModel
from nodescraper.plugins.inband.amdsmi.amdsmi_collector import AmdSmiCollector
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiListItem,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiVersion,
    BadPages,
    Fw,
    Partition,
    Processes,
    Topo,
    XgmiLinks,
    XgmiMetrics,
)
from nodescraper.plugins.inband.amdsmi.collector_args import AmdSmiCollectorArgs
from nodescraper.utils import get_exception_details, get_exception_traceback

from .amdsmidata_flavor import AmdSmiFlavorDataModel
from .amdsmidata_guest import GuestAmdSmiMetric, GuestAmdSmiStatic
from .amdsmidata_host import (
    HostDriverAmdSmiListItem,
    HostDriverAmdSmiMetric,
    HostDriverAmdSmiStatic,
    HostDriverAmdSmiVersion,
    HostDriverBadPages,
    HostDriverTopo,
    HostDriverXgmiLinks,
    HostDriverXgmiMetrics,
)

AMD_SMI_CPER_FOLDER = "/tmp/amd_smi_cper"


class AmdSmiFlavorCollector(AmdSmiCollector):
    """amd-smi collector with host/guest driver-flavor support (incl. ESXi mxGPU)."""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX, OSFamily.ESXI}
    DATA_MODEL = AmdSmiFlavorDataModel  # type: ignore[assignment]

    # amd-smi runs with any of these drivers; the driver sets the CLI/JSON flavor.
    _HOST_DRIVER_MODULES = ("gim", "amdgpuv")
    _GUEST_DRIVER_MODULES = ("amdgpu",)

    # ---- driver-flavor detection --------------------------------------------------

    def _get_loaded_gpu_driver(self) -> Optional[str]:
        """Loaded AMD GPU driver module name (gim/amdgpuv/amdgpu), or None. Cached."""
        cached = getattr(self, "_loaded_gpu_driver_cache", None)
        if cached is not None:
            return cached
        if self.system_info.os_family == OSFamily.ESXI:
            cmd_ret = self._run_sut_cmd("vmkload_mod -l")
        else:
            cmd_ret = self._run_sut_cmd("lsmod", sudo=True)
        if cmd_ret.exit_code != 0:
            return None
        known = self._HOST_DRIVER_MODULES + self._GUEST_DRIVER_MODULES
        driver: Optional[str] = None
        for line in cmd_ret.stdout.splitlines():
            module = line.strip().split()[0] if line.strip() else ""
            if module in known:
                driver = module
                break
        self._loaded_gpu_driver_cache = driver
        return driver

    def _check_gpu_driver_loaded(self) -> bool:
        """A driver is required for all amd-smi commands (including help/version)."""
        return self._get_loaded_gpu_driver() is not None

    @property
    def is_host_driver(self) -> bool:
        """True for the mxGPU host driver (gim on Linux, amdgpuv on ESXi)."""
        return self._get_loaded_gpu_driver() in self._HOST_DRIVER_MODULES

    def _is_virtualized(self) -> bool:
        """True inside a virtualized guest (VM), via the CPU hypervisor flag. Cached."""
        cached = getattr(self, "_is_virtualized_cache", None)
        if cached is not None:
            return cached
        if self.system_info.os_family == OSFamily.ESXI:
            self._is_virtualized_cache = False
            return False
        cmd_ret = self._run_sut_cmd("grep -c hypervisor /proc/cpuinfo")
        try:
            value = int(cmd_ret.stdout.strip()) > 0
        except (ValueError, AttributeError):
            value = False
        self._is_virtualized_cache = value
        return value

    @property
    def is_guest_driver(self) -> bool:
        """True for a guest-VF amdgpu (amdgpu inside a VM). Bare-metal amdgpu is not guest."""
        return not self.is_host_driver and self._is_virtualized()

    @property
    def _amd_smi_needs_sudo(self) -> bool:
        """amd-smi needs sudo on Linux (guest + mxGPU host); not on ESXi (no sudo binary)."""
        return self.system_info.os_family != OSFamily.ESXI

    # ---- command execution --------------------------------------------------------

    def _run_amd_smi(self, cmd: str, sudo: Optional[bool] = None) -> Optional[str]:
        """Run amd-smi, elevating on Linux by default (ESXi needs no sudo)."""
        if sudo is None:
            sudo = self._amd_smi_needs_sudo
        cmd_ret = self._run_sut_cmd(f"{self.AMD_SMI_EXE} {cmd}", sudo=sudo)
        # Host amd-smi reports a benign "no data" status on stderr with rc=0 (e.g.
        # bad-pages when none exist) — a valid empty result, not an error.
        if cmd_ret.exit_code == 0 and "No data was found" in cmd_ret.stderr:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amd-smi returned no data for command",
                data={"command": cmd, "stderr": cmd_ret.stderr},
                priority=EventPriority.INFO,
            )
            return None
        if cmd_ret.stderr != "" or cmd_ret.exit_code != 0:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi command",
                data={"command": cmd, "exit_code": cmd_ret.exit_code, "stderr": cmd_ret.stderr},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return None
        return cmd_ret.stdout

    def _run_amd_smi_dict(
        self,
        cmd: str,
        sudo: Optional[bool] = None,
        raise_event: bool = True,
        *,
        patch_invalid_json: bool = False,
    ) -> Union[dict, list, None]:
        """Run an amd-smi command with --json and parse the output."""
        cmd += " --json"
        cmd_ret = self._run_amd_smi(cmd, sudo=sudo)
        if not cmd_ret:
            return None
        try:
            if patch_invalid_json:
                # amd-smi has been observed to emit invalid JSON ("]\n[") between records.
                cmd_ret = cmd_ret.replace("]\n[", ",")
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

    def _check_command_supported(self, command: str) -> bool:
        """Log an INFO event when amd-smi help does not list the command."""
        if command not in getattr(self, "amd_smi_commands", set()):
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"amd-smi does not support command: `{command}`",
                priority=EventPriority.INFO,
            )
            return False
        return True

    def detect_amdsmi_commands(self) -> set[str]:
        """Parse `amd-smi help` (host) / `amd-smi -h` (guest) for supported commands."""
        command_pattern = re.compile(r"^\s{4}([\w\-]+)\s", re.MULTILINE)
        help_flag = "help" if self.is_host_driver else "-h"
        help_output = self._run_amd_smi(help_flag)
        if help_output is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error running amd-smi help command",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return set()
        return set(command_pattern.findall(help_output))

    # ---- model builder ------------------------------------------------------------

    def _build_flavor_model(
        self,
        model_class: type[BaseModel],
        json_data: Union[dict, list, None],
        *,
        return_first: bool = False,
        keep_key: Optional[str] = None,
    ) -> Any:
        """Validate raw amd-smi JSON into ``model_class`` (per-flavor class chosen by caller).

        keep_key drops rows missing that key (host list/topology enumerate non-GPU rows);
        return_first collapses to a single record (e.g. version).
        """
        if json_data is None:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=f"No data to build model: {model_class.__name__}",
                priority=EventPriority.ERROR,
            )
            return None
        if isinstance(json_data, dict):
            try:
                return model_class.model_validate(json_data)
            except ValidationError as e:
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Failed to build amd-smi model: {model_class.__name__}",
                    data=get_exception_details(e),
                    priority=EventPriority.WARNING,
                )
                return None

        # Build per row so one unparseable entry doesn't discard the whole list. A
        # guest amd-smi can enumerate a VF's secondary PCI functions (bdf .1-.7) as
        # all-N/A rows alongside the real GPUs; skip those but keep the real ones.
        validated: list = []
        skipped: list = []
        for item in json_data:
            if not isinstance(item, dict):
                self._log_event(
                    category=EventCategory.APPLICATION,
                    description=f"Invalid data type for amd-smi model: {model_class.__name__}",
                    data={"data_type": type(item).__name__},
                    priority=EventPriority.WARNING,
                )
                return None
            if keep_key is not None and keep_key not in item:
                continue
            try:
                validated.append(model_class.model_validate(item))
            except ValidationError as e:
                skipped.append(get_exception_details(e))
        if skipped:
            self._log_event(
                category=EventCategory.APPLICATION,
                description=(
                    f"Skipped {len(skipped)} unparseable {model_class.__name__} "
                    f"row(s); kept {len(validated)}"
                ),
                data={"first_error": skipped[0]},
                priority=EventPriority.WARNING,
            )
        if return_first:
            return validated[0] if validated else None
        return validated

    # ---- raw-JSON getters (flavor-aware commands) --------------------------------

    def _get_amdsmi_version(self) -> Union[AmdSmiVersion, HostDriverAmdSmiVersion, None]:  # type: ignore[override]
        """Pick the version model by flavor (host nests fields under a "version" key)."""
        ret = self._run_amd_smi_dict("version")
        model = HostDriverAmdSmiVersion if self.is_host_driver else AmdSmiVersion
        return self._build_flavor_model(model, ret, return_first=True)

    def get_gpu_list(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("list"):
            return None
        return self._run_amd_smi_dict("list", patch_invalid_json=True)

    def get_process(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("process"):
            return None
        return self._run_amd_smi_dict("process")

    _PARTITION_COLUMNS = (
        "gpu_id",
        "memory",
        "accelerator_type",
        "accelerator_profile_index",
        "partition_id",
    )

    def get_partition(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("partition"):
            return None
        # Host-driver amd-smi has no --json for partition; parse the text table.
        if self.is_host_driver:
            return self._get_partition_host()
        return self._run_amd_smi_dict("partition")

    def _get_partition_host(self) -> Optional[dict]:
        """Parse host `partition -c` text (--json unsupported on gim/amdgpuv)."""
        raw = self._run_amd_smi("partition -c")
        if raw is None:
            return None
        lines = raw.splitlines()
        header_index = None
        for index, line in enumerate(lines):
            columns = line.split()
            if columns and columns[0] == "GPU":
                header_index = index
                break
        if header_index is None:
            return None
        current_partitions = []
        for line in lines[header_index + 1 :]:
            columns = line.split()
            is_data_row = len(columns) >= len(self._PARTITION_COLUMNS) and columns[0].isdigit()
            if not is_data_row:
                break
            partition: dict[str, object] = dict(zip(self._PARTITION_COLUMNS, columns))
            partition["gpu_id"] = int(str(partition["gpu_id"]))
            current_partitions.append(partition)
        if not current_partitions:
            return None
        return {"current_partition": current_partitions}

    def get_topology(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("topology"):
            return None
        return self._run_amd_smi_dict("topology")

    def get_static(self) -> Union[list, None]:
        if not self._check_command_supported("static"):
            return None
        # Host-driver amd-smi does not accept "-g all".
        static_sub_cmd = "static" if self.is_host_driver else "static -g all"
        static_data = self._run_amd_smi_dict(static_sub_cmd)
        if static_data is None:
            return None
        if isinstance(static_data, dict) and "gpu_data" in static_data:
            static_data = static_data["gpu_data"]
        return [s for s in static_data if isinstance(s, dict) and "gpu" in s]

    def get_metric(self) -> Union[list, None]:
        if not self._check_command_supported("metric"):
            return None
        metric_sub_cmd = "metric" if self.is_host_driver else "metric -g all"
        metric_data = self._run_amd_smi_dict(metric_sub_cmd)
        if metric_data is None:
            return None
        if isinstance(metric_data, dict) and "gpu_data" in metric_data:
            metric_data = metric_data["gpu_data"]
        return [m for m in metric_data if isinstance(m, dict) and "gpu" in m]

    def get_firmware(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("firmware"):
            return None
        return self._run_amd_smi_dict("firmware")

    def get_bad_pages(self) -> Union[dict, list, None]:  # type: ignore[override]
        if not self._check_command_supported("bad-pages"):
            return None
        return self._run_amd_smi_dict("bad-pages")

    def get_xgmi_data_metric(self) -> Optional[dict]:
        """Fetch xgmi metric + link data (host uses --metric/--link-status vs guest -m/-l)."""
        if not self._check_command_supported("xgmi"):
            return None
        metric_flag = "--metric" if self.is_host_driver else "-m"
        xgmi_metric_data = self._run_amd_smi_dict(f"xgmi {metric_flag}")
        if xgmi_metric_data is None:
            xgmi_metric_data = []
        elif isinstance(xgmi_metric_data, dict) and "xgmi_metric" in xgmi_metric_data:
            xgmi_metric_data = xgmi_metric_data["xgmi_metric"]
            if isinstance(xgmi_metric_data, list) and len(xgmi_metric_data) == 1:
                xgmi_metric_data = xgmi_metric_data[0]

        link_flag = "--link-status" if self.is_host_driver else "-l"
        xgmi_link_data = self._run_amd_smi_dict(f"xgmi {link_flag}", raise_event=False)
        if isinstance(xgmi_link_data, dict) and "link_status" in xgmi_link_data:
            xgmi_link_data = xgmi_link_data["link_status"]
        if xgmi_link_data is None:
            xgmi_link_data = []
        return {"metric": xgmi_metric_data, "link": xgmi_link_data}

    def get_cper_data(self) -> tuple[list[FileModel], dict[str, int]]:
        """Collect CPER files. Host amd-smi requires --severity; guest/bare-metal do not."""
        if not self._check_command_supported("ras"):
            return [], {}
        self._run_sut_cmd(
            f"mkdir -p {AMD_SMI_CPER_FOLDER} && rm -f {AMD_SMI_CPER_FOLDER}/*.cper "
            f"&& rm -f {AMD_SMI_CPER_FOLDER}/*.json",
            sudo=False,
        )
        if self.is_host_driver:
            cper_sub_cmd = f"ras --cper --severity=all --folder={AMD_SMI_CPER_FOLDER}"
        else:
            cper_sub_cmd = f"ras --cper --folder={AMD_SMI_CPER_FOLDER}"
        cper_out = self._run_amd_smi(cper_sub_cmd)
        if cper_out is None or not re.findall(r"(\w+\.cper)", cper_out):
            return [], {}
        self._run_sut_cmd(
            f"tar -czf {AMD_SMI_CPER_FOLDER}.tar.gz -C {AMD_SMI_CPER_FOLDER} .",
            sudo=self._amd_smi_needs_sudo,
        )
        cper_zip = self._read_sut_file(
            f"{AMD_SMI_CPER_FOLDER}.tar.gz", encoding=None, strip=False, log_artifact=True
        )
        if not hasattr(cper_zip, "contents"):
            return [], {}
        io_bytes = io.BytesIO(cper_zip.contents)  # type: ignore[attr-defined]
        cper_data: list[FileModel] = []
        cper_afids: dict[str, int] = {}
        try:
            with TarFile.open(fileobj=io_bytes, mode="r:gz") as tar_file:
                for member in tar_file.getmembers():
                    if not (member.isfile() and member.name.endswith(".cper")):
                        continue
                    content = tar_file.extractfile(member)
                    file_bytes = content.read() if content is not None else b""
                    cper_data.append(FileModel(file_contents=file_bytes, file_name=member.name))
                    afid = self._get_cper_afid(f"{AMD_SMI_CPER_FOLDER}/{member.name}")
                    if afid is not None:
                        cper_afids[member.name] = afid
        except Exception as e:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Error extracting cper data",
                data={"exception": get_exception_traceback(e)},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            return [], {}
        if cper_data:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="CPER data has been extracted from amd-smi",
                data={"cper_count": len(cper_data), "afid_count": len(cper_afids)},
                priority=EventPriority.INFO,
            )
        return cper_data, cper_afids

    # ---- orchestration ------------------------------------------------------------

    def _get_amdsmi_data(
        self, args: Optional[AmdSmiCollectorArgs] = None
    ) -> Optional[AmdSmiFlavorDataModel]:
        """Fetch all amd-smi sub-data and build the model with per-flavor variants."""
        try:
            version = self._get_amdsmi_version()
            gpu_list = self.get_gpu_list()
            processes = self.get_process()
            partition = self.get_partition()
            firmware = self.get_firmware()
            topology = self.get_topology()
            amdsmi_static = self.get_static()
            amdsmi_metric = self.get_metric()
            bad_pages = self.get_bad_pages()
            xgmi = self.get_xgmi_data_metric() or {"metric": [], "link": []}
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

        host = self.is_host_driver
        guest = self.is_guest_driver

        # list / topology / bad-pages / xgmi split host vs non-host.
        if host:
            list_item_cls: type[BaseModel] = HostDriverAmdSmiListItem
            topo_cls: type[BaseModel] = HostDriverTopo
            bad_pages_cls: type[BaseModel] = HostDriverBadPages
            xgmi_metric_cls: type[BaseModel] = HostDriverXgmiMetrics
            xgmi_link_cls: type[BaseModel] = HostDriverXgmiLinks
        else:
            list_item_cls = AmdSmiListItem
            topo_cls = Topo
            bad_pages_cls = BadPages
            xgmi_metric_cls = XgmiMetrics
            xgmi_link_cls = XgmiLinks

        # static / metric are three-way (a guest VF omits physical fields).
        if host:
            static_cls: type[BaseModel] = HostDriverAmdSmiStatic
            metric_cls: type[BaseModel] = HostDriverAmdSmiMetric
        elif guest:
            static_cls = GuestAmdSmiStatic
            metric_cls = GuestAmdSmiMetric
        else:
            static_cls = AmdSmiStatic
            metric_cls = AmdSmiMetric

        gpu_list_model = self._build_flavor_model(list_item_cls, gpu_list, keep_key="gpu")
        topo_model = self._build_flavor_model(topo_cls, topology, keep_key="gpu")
        bad_pages_model = self._build_flavor_model(bad_pages_cls, bad_pages) if bad_pages else []
        partition_model = self._build_flavor_model(Partition, partition)
        # Host-driver amd-smi has no `process` command; avoid a spurious error.
        process_model = self._build_flavor_model(Processes, processes) if processes else []
        firmware_model = self._build_flavor_model(Fw, firmware)
        static_model = self._build_flavor_model(static_cls, amdsmi_static)
        metric_model = self._build_flavor_model(metric_cls, amdsmi_metric)
        xgmi_metric_model = self._build_flavor_model(xgmi_metric_cls, xgmi["metric"])
        xgmi_link_model = self._build_flavor_model(xgmi_link_cls, xgmi["link"])

        try:
            fw_ids = args.analysis_firmware_ids if args and args.analysis_firmware_ids else None
            base = AmdSmiFlavorDataModel(
                version=version,
                gpu_list=gpu_list_model or [],
                process=process_model or [],
                partition=partition_model,
                firmware=firmware_model or [],
                static=static_model or [],
                topology=topo_model or [],
                metric=metric_model or [],
                bad_pages=bad_pages_model or [],
                xgmi_metric=xgmi_metric_model or [],
                xgmi_link=xgmi_link_model or [],
                cper_data=cper_data,
                cper_afids=cper_afids,
                analysis_firmware_ids=fw_ids,
                analysis_ref=None,
            )
            return base.model_copy(update={"analysis_ref": base.build_analysis_ref()})
        except ValidationError as err:
            self._log_event(
                category=EventCategory.APPLICATION,
                description="Failed to build AmdSmiFlavorDataModel",
                data={"errors": err.errors(include_url=False)},
                priority=EventPriority.ERROR,
            )
            return None

    def collect_data(
        self, args: Optional[AmdSmiCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[AmdSmiFlavorDataModel]]:
        """Collect amd-smi data across driver flavors (guest/bare-metal/host, incl. ESXi)."""
        if not self._check_amdsmi_installed() or not self._check_gpu_driver_loaded():
            self._log_event(
                category=EventCategory.APPLICATION,
                description="amd-smi not installed or no AMD GPU driver loaded",
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None
        try:
            self.amd_smi_commands = self.detect_amdsmi_commands()
            amd_smi_data = self._get_amdsmi_data(args)
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
