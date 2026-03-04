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
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .collector_args import NicCollectorArgs
from .nic_data import (
    NicCliDevice,
    NicCliQos,
    NicCliQosAppEntry,
    NicCommandResult,
    NicCtlCard,
    NicCtlCardShow,
    NicCtlDcqcn,
    NicCtlEnvironment,
    NicCtlLif,
    NicCtlPort,
    NicCtlQos,
    NicCtlRdma,
    NicCtlVersion,
    NicDataModel,
    PensandoNicCard,
    PensandoNicDcqcn,
    PensandoNicEnvironment,
    PensandoNicLif,
    PensandoNicPcieAts,
    PensandoNicPort,
    PensandoNicQos,
    PensandoNicQosScheduling,
    PensandoNicRdmaStatistic,
    PensandoNicRdmaStatistics,
    PensandoNicVersionFirmware,
    PensandoNicVersionHostSoftware,
    command_to_canonical_key,
)

# Default commands: niccli (Broadcom) and nicctl (Pensando). Use {device_num} and {card_id} placeholders.
NICCLI_LIST_CMD = "niccli --list"
NICCLI_LIST_DEVICES_CMD = "niccli --list_devices"
NICCLI_DISCOVERY_CMDS = [
    NICCLI_LIST_DEVICES_CMD,
    NICCLI_LIST_CMD,
]
# Command template for support_rdma;
NICCLI_SUPPORT_RDMA_CMD_TEMPLATE = "niccli -dev {device_num} nvm -getoption support_rdma -scope 0"
NICCLI_PER_DEVICE_TEMPLATES = [
    NICCLI_SUPPORT_RDMA_CMD_TEMPLATE,
    "niccli -dev {device_num} nvm -getoption performance_profile",
    "niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering",
    "niccli -dev {device_num} getqos",
]
# Text-format command for card discovery and pensando_nic_cards (no --json).
NICCTL_CARD_TEXT_CMD = "nicctl show card"
NICCTL_GLOBAL_COMMANDS = [
    "nicctl --version",
    "nicctl show card flash partition --json",
    "nicctl show card interrupts --json",
    "nicctl show card logs --non-persistent",
    "nicctl show card logs --boot-fault",
    "nicctl show card logs --persistent",
    "nicctl show card profile --json",
    "nicctl show card time --json",
    "nicctl show card statistics packet-buffer summary --json",
    "nicctl show lif statistics --json",
    "nicctl show lif internal queue-to-ud-pinning",
    "nicctl show pipeline internal anomalies",
    "nicctl show pipeline internal rsq-ring",
    "nicctl show pipeline internal statistics memory",
    "nicctl show port fsm",
    "nicctl show port transceiver --json",
    "nicctl show port statistics --json",
    "nicctl show port internal mac",
    "nicctl show qos headroom --json",
    "nicctl show rdma queue --json",
    "nicctl show rdma queue-pair --detail --json",
    "nicctl show version firmware",
]
NICCTL_PER_CARD_TEMPLATES = [
    "nicctl show dcqcn --card {card_id} --json",
    "nicctl show card hardware-config --card {card_id}",
]

# Legacy text-format commands for Pensando (no --json); parsed by _parse_nicctl_* into pensando_nic_*.
NICCTL_LEGACY_TEXT_COMMANDS = [
    "nicctl show card",
    "nicctl show dcqcn",
    "nicctl show environment",
    "nicctl show lif",
    "nicctl show pcie ats",
    "nicctl show port",
    "nicctl show qos",
    "nicctl show rdma statistics",
    "nicctl show version host-software",
]

# Max lengths for fields included in the serialized datamodel (keeps nicclidatamodel.json small).
MAX_COMMAND_LENGTH_IN_DATAMODEL = 256
MAX_STDERR_LENGTH_IN_DATAMODEL = 512


# Commands whose output is very long; store only as file artifacts, not in data model.
def _is_artifact_only_command(cmd: str) -> bool:
    c = cmd.strip()
    if c.startswith("nicctl show card logs "):
        return True
    if "nicctl show card hardware-config --card " in c:
        return True
    if c == "nicctl show port fsm":
        return True
    if c.startswith("nicctl show pipeline internal "):
        return True
    if c == "nicctl show rdma queue-pair --detail --json":
        return True
    if c == "nicctl show lif internal queue-to-ud-pinning":
        return True
    if c == "nicctl show port internal mac":
        return True
    return False


def _merged_canonical_key(cmd: str) -> str:
    """Return a single canonical key for commands that collect the same data."""
    if cmd in NICCLI_DISCOVERY_CMDS:
        return "niccli_discovery"
    return command_to_canonical_key(cmd)


def _default_commands() -> List[str]:
    """Return the default flat list of command templates (with placeholders)."""
    out: List[str] = [NICCLI_LIST_CMD]
    for t in NICCLI_PER_DEVICE_TEMPLATES:
        out.append(t)
    for c in NICCTL_GLOBAL_COMMANDS:
        out.append(c)
    for t in NICCTL_PER_CARD_TEMPLATES:
        out.append(t)
    return out


def _parse_niccli_qos_app_entries(stdout: str) -> List[NicCliQosAppEntry]:
    """Parse APP# blocks from niccli qos output into NicCliQosAppEntry list."""
    entries: List[NicCliQosAppEntry] = []
    current: Optional[NicCliQosAppEntry] = None
    for line in stdout.splitlines():
        line = line.strip()
        if re.match(r"APP#\d+", line, re.I):
            if current is not None:
                entries.append(current)
            current = NicCliQosAppEntry()
            continue
        if current is None or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if "priority" in key:
            try:
                current.priority = int(val)
            except ValueError:
                pass
        elif key == "sel":
            try:
                current.sel = int(val)
            except ValueError:
                pass
        elif key == "dscp":
            try:
                current.dscp = int(val)
            except ValueError:
                pass
        elif key == "port":
            try:
                current.port = int(val)
            except ValueError:
                pass
        elif (
            key in ("tcp", "udp", "dccp")
            or "protocol" in key
            or "udp" in key
            or "tcp" in key
            or "dccp" in key
        ):
            if val and not val.isdigit():
                current.protocol = val
            else:
                current.protocol = {"udp or dccp": "UDP or DCCP"}.get(
                    key, key.replace("_", " ").title()
                )
            if val:
                try:
                    current.port = int(val)
                except ValueError:
                    pass
    if current is not None:
        entries.append(current)
    return entries


def _parse_niccli_device_numbers(stdout: str) -> List[int]:
    """Parse device numbers from niccli --list or --list_devices output.
    Looks for lines like '1) Model' or '1 )' to extract device index.
    """
    device_nums: List[int] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\s*\)", line)
        if match:
            try:
                device_nums.append(int(match.group(1)))
            except ValueError:
                continue
    return sorted(set(device_nums))


def _parse_nicctl_card_ids(stdout: str) -> List[str]:
    """Parse card IDs from nicctl show card --json output.
    Expects JSON: either a list of objects with 'id'/'card_id' or an object with a list.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    ids: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cid = item.get("id") or item.get("card_id") or item.get("CardId")
                if cid is not None:
                    ids.append(str(cid))
    elif isinstance(data, dict):
        cards = data.get("cards") or data.get("Cards") or data.get("card") or data.get("data")
        if isinstance(cards, list):
            for item in cards:
                if isinstance(item, dict):
                    cid = item.get("id") or item.get("card_id") or item.get("CardId")
                    if cid is not None:
                        ids.append(str(cid))
        cid = data.get("id") or data.get("card_id")
        if cid is not None and str(cid) not in ids:
            ids.append(str(cid))
    return ids


def _card_list_items(data: Any) -> List[Any]:
    """Return list of card item dicts from parsed nicctl show card --json."""
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        cards = data.get("cards") or data.get("Cards") or data.get("card") or data.get("data")
        if isinstance(cards, list):
            return [x for x in cards if isinstance(x, dict)]
    return []


def _find_card_info(card_list: List[Any], card_id: str) -> Optional[Any]:
    """Return the card item dict whose id/card_id matches card_id."""
    for item in card_list:
        cid = item.get("id") or item.get("card_id") or item.get("CardId")
        if cid is not None and str(cid) == str(card_id):
            return item
    return None


def _build_structured(
    results: Dict[str, NicCommandResult],
    parsed: Dict[str, Any],
    card_ids: List[str],
    card_list_override: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[
    Optional[NicCtlCardShow],
    List[NicCtlCard],
    Optional[NicCtlPort],
    Optional[NicCtlLif],
    Optional[NicCtlQos],
    Optional[NicCtlRdma],
    Optional[NicCtlDcqcn],
    Optional[NicCtlEnvironment],
    Optional[NicCtlVersion],
]:
    """Build structured domain objects from results and parsed dicts."""

    def _p(cmd: str) -> Any:
        return parsed.get(cmd)

    def _r(cmd: str) -> Optional[NicCommandResult]:
        return results.get(cmd)

    def _stdout(cmd: str) -> str:
        r = _r(cmd)
        return (r.stdout or "") if r else ""

    card_list = (
        card_list_override
        if card_list_override is not None
        else _card_list_items(_p("nicctl show card --json"))
    )
    cards: List[NicCtlCard] = []
    for cid in card_ids:
        info = _find_card_info(card_list, cid)
        hw_cmd = f"nicctl show card hardware-config --card {cid}"
        dcqcn_cmd = f"nicctl show dcqcn --card {cid} --json"
        cards.append(
            NicCtlCard(
                card_id=cid,
                info=info,
                hardware_config=_stdout(hw_cmd) or None,
                dcqcn=_p(dcqcn_cmd),
            )
        )

    card_show = NicCtlCardShow(
        flash_partition=_p("nicctl show card flash partition --json"),
        interrupts=_p("nicctl show card interrupts --json"),
        logs_non_persistent=_stdout("nicctl show card logs --non-persistent") or None,
        logs_boot_fault=_stdout("nicctl show card logs --boot-fault") or None,
        logs_persistent=_stdout("nicctl show card logs --persistent") or None,
        profile=_p("nicctl show card profile --json"),
        time=_p("nicctl show card time --json"),
        statistics_packet_buffer_summary=_p(
            "nicctl show card statistics packet-buffer summary --json"
        ),
    )

    port = NicCtlPort(
        port=_p("nicctl show port"),
        port_fsm=_stdout("nicctl show port fsm") or None,
        port_transceiver=_p("nicctl show port transceiver --json"),
        port_statistics=_p("nicctl show port statistics --json"),
        port_internal_mac=_stdout("nicctl show port internal mac") or None,
    )
    lif = NicCtlLif(
        lif=_p("nicctl show lif"),
        lif_statistics=_p("nicctl show lif statistics --json"),
        lif_internal_queue_to_ud_pinning=_stdout("nicctl show lif internal queue-to-ud-pinning")
        or None,
    )
    qos = NicCtlQos(
        qos=_p("nicctl show qos"),
        qos_headroom=_p("nicctl show qos headroom --json"),
    )
    rdma = NicCtlRdma(
        rdma_queue=_p("nicctl show rdma queue --json"),
        rdma_queue_pair_detail=_p("nicctl show rdma queue-pair --detail --json"),
        rdma_statistics=_p("nicctl show rdma statistics"),
    )
    dcqcn = NicCtlDcqcn(dcqcn_global=_p("nicctl show dcqcn"))
    environment = NicCtlEnvironment(environment=_p("nicctl show environment"))
    version = NicCtlVersion(
        version=_stdout("nicctl --version") or None,
        version_firmware=_stdout("nicctl show version firmware") or None,
    )
    return card_show, cards, port, lif, qos, rdma, dcqcn, environment, version


class NicCollector(InBandDataCollector[NicDataModel, NicCollectorArgs]):
    """Collect raw output from niccli (Broadcom) and nicctl (Pensando) commands."""

    DATA_MODEL = NicDataModel

    def collect_data(
        self,
        args: Optional[NicCollectorArgs] = None,
    ) -> Tuple[TaskResult, Optional[NicDataModel]]:
        """Run niccli/nicctl commands and store stdout/stderr/exit_code per command."""
        use_sudo_niccli = args.use_sudo_niccli if args else True
        use_sudo_nicctl = args.use_sudo_nicctl if args else True
        custom_commands = args.commands if args and args.commands else None

        results: dict[str, NicCommandResult] = {}

        # Discovery: device numbers from niccli
        device_nums: List[int] = []
        for list_cmd in NICCLI_DISCOVERY_CMDS:
            res = self._run_sut_cmd(list_cmd, sudo=use_sudo_niccli)
            results[list_cmd] = NicCommandResult(
                command=list_cmd,
                stdout=res.stdout or "",
                stderr=res.stderr or "",
                exit_code=res.exit_code,
            )
            if res.exit_code == 0 and res.stdout:
                device_nums = _parse_niccli_device_numbers(res.stdout)
                if device_nums:
                    break

        # Discovery: card IDs from nicctl show card (text); same output used for pensando_nic_cards
        card_ids: List[str] = []
        card_list_from_text: List[Dict[str, Any]] = []
        res_card = self._run_sut_cmd(NICCTL_CARD_TEXT_CMD, sudo=use_sudo_nicctl)
        results[NICCTL_CARD_TEXT_CMD] = NicCommandResult(
            command=NICCTL_CARD_TEXT_CMD,
            stdout=res_card.stdout or "",
            stderr=res_card.stderr or "",
            exit_code=res_card.exit_code,
        )
        if res_card.exit_code == 0 and res_card.stdout:
            legacy_cards = self._parse_nicctl_card(res_card.stdout)
            card_ids = [c.id for c in legacy_cards]
            card_list_from_text = [c.model_dump() for c in legacy_cards]

        # Build full command list (expand placeholders)
        if custom_commands is not None:
            commands_to_run: List[str] = []
            for tpl in custom_commands:
                if "{device_num}" in tpl:
                    for d in device_nums:
                        commands_to_run.append(tpl.format(device_num=d))
                elif "{card_id}" in tpl:
                    for c in card_ids:
                        commands_to_run.append(tpl.format(card_id=c))
                else:
                    commands_to_run.append(tpl)
        else:
            commands_to_run = []
            # niccli list already stored
            for tpl in NICCLI_PER_DEVICE_TEMPLATES:
                for d in device_nums:
                    commands_to_run.append(tpl.format(device_num=d))
            # nicctl global (card discovery already done via NICCTL_CARD_TEXT_CMD)
            for c in NICCTL_GLOBAL_COMMANDS:
                commands_to_run.append(c)
            for tpl in NICCTL_PER_CARD_TEMPLATES:
                for cid in card_ids:
                    commands_to_run.append(tpl.format(card_id=cid))
            for cmd in NICCTL_LEGACY_TEXT_COMMANDS:
                commands_to_run.append(cmd)

        # Run each command and store (artifact-only commands are not added to results / data model).
        for cmd in commands_to_run:
            if cmd in results:
                continue
            is_niccli = cmd.strip().startswith("niccli")
            sudo = use_sudo_niccli if is_niccli else use_sudo_nicctl
            res = self._run_sut_cmd(cmd, sudo=sudo)
            if _is_artifact_only_command(cmd):
                if res.exit_code != 0:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"niccli/nicctl command failed: {cmd}",
                        data={"exit_code": res.exit_code, "stderr": (res.stderr or "")[:500]},
                        priority=EventPriority.WARNING,
                    )
                continue
            results[cmd] = NicCommandResult(
                command=cmd,
                stdout=res.stdout or "",
                stderr=res.stderr or "",
                exit_code=res.exit_code,
            )
            if res.exit_code != 0:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"niccli/nicctl command failed: {cmd}",
                    data={"exit_code": res.exit_code, "stderr": (res.stderr or "")[:500]},
                    priority=EventPriority.WARNING,
                )

        # Parse JSON for building structured domain objects (artifact-only commands have no stdout, so not in parsed).
        parsed: Dict[str, Any] = {}
        for cmd, r in results.items():
            if r.exit_code != 0 or not (r.stdout or "").strip():
                continue
            try:
                parsed[cmd] = json.loads(r.stdout.strip())
            except (ValueError, TypeError):
                pass

        # Build structured domain objects from JSON/raw output (card_show/cards from text when present).
        (
            card_show,
            cards,
            port,
            lif,
            qos,
            rdma,
            dcqcn,
            environment,
            version,
        ) = _build_structured(
            results, parsed, card_ids, card_list_override=card_list_from_text or None
        )

        # card_show and cards (can be large) go to TextFileArtifacts; excluded from datamodel.
        if card_show is not None:
            self.result.artifacts.append(
                TextFileArtifact(
                    filename="niccli_card_show.json",
                    contents=card_show.model_dump_json(indent=2),
                )
            )
        if cards:
            self.result.artifacts.append(
                TextFileArtifact(
                    filename="niccli_cards.json",
                    contents=json.dumps([c.model_dump(mode="json") for c in cards], indent=2),
                )
            )

        # Serialized nicclidatamodel.json: no stdout in results, truncated command/stderr (keeps file small).
        # Command output lives on disk from _run_sut_cmd; model keeps only command identity and status.
        def _truncate(s: str, max_len: int) -> str:
            if not s or len(s) <= max_len:
                return s or ""
            return s[: max_len - 3] + "..."

        results_for_model = {
            cmd: NicCommandResult(
                command=_truncate(r.command, MAX_COMMAND_LENGTH_IN_DATAMODEL),
                stdout="",
                stderr=_truncate(r.stderr or "", MAX_STDERR_LENGTH_IN_DATAMODEL),
                exit_code=r.exit_code,
            )
            for cmd, r in results.items()
        }

        # Legacy text parsers: populate broadcom_nic_* and pensando_nic_* for the datamodel.
        broadcom_devices, broadcom_qos_data, broadcom_support_rdma = (
            self._collect_broadcom_nic_structured(results)
        )
        (
            pensando_cards,
            pensando_dcqcn,
            pensando_environment,
            pensando_lif,
            pensando_pcie_ats,
            pensando_ports,
            pensando_qos,
            pensando_rdma_statistics,
            pensando_version_host_software,
            pensando_version_firmware,
        ) = self._collect_pensando_nic_structured(results)

        if not results or all(r.exit_code != 0 for r in results.values()):
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            self.result.message = "All niccli/nicctl commands failed or no commands were run"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = f"Collected {len(results)} niccli/nicctl command results"
        return self.result, NicDataModel(
            results=results_for_model,
            card_show=None,
            cards=[],
            port=port,
            lif=lif,
            qos=qos,
            rdma=rdma,
            dcqcn=dcqcn,
            environment=environment,
            version=version,
            broadcom_nic_devices=broadcom_devices,
            broadcom_nic_qos=broadcom_qos_data,
            broadcom_nic_support_rdma=broadcom_support_rdma,
            pensando_nic_cards=pensando_cards,
            pensando_nic_dcqcn=pensando_dcqcn,
            pensando_nic_environment=pensando_environment,
            pensando_nic_lif=pensando_lif,
            pensando_nic_pcie_ats=pensando_pcie_ats,
            pensando_nic_ports=pensando_ports,
            pensando_nic_qos=pensando_qos,
            pensando_nic_rdma_statistics=pensando_rdma_statistics,
            pensando_nic_version_host_software=pensando_version_host_software,
            pensando_nic_version_firmware=pensando_version_firmware,
        )

    def _collect_broadcom_nic_structured(
        self, results: Dict[str, NicCommandResult]
    ) -> Tuple[List[NicCliDevice], Dict[int, NicCliQos], Dict[int, str]]:
        """Build niccli (Broadcom) structured data from results using legacy text parsers."""
        devices: List[NicCliDevice] = []
        qos_data: Dict[int, NicCliQos] = {}
        support_rdma: Dict[int, str] = {}
        list_stdout: Optional[str] = None
        for list_cmd in NICCLI_DISCOVERY_CMDS:
            r = results.get(list_cmd)
            if r and r.exit_code == 0 and (r.stdout or "").strip():
                list_stdout = r.stdout
                break
        if not list_stdout:
            return devices, qos_data, support_rdma
        devices = self._parse_niccli_listdev(list_stdout)
        for device in devices:
            cmd = f"niccli -dev {device.device_num} getqos"
            r = results.get(cmd)
            if r and r.exit_code == 0 and (r.stdout or "").strip():
                qos_data[device.device_num] = self._parse_niccli_qos(
                    device.device_num, r.stdout or ""
                )
            support_rdma_cmd = NICCLI_SUPPORT_RDMA_CMD_TEMPLATE.format(device_num=device.device_num)
            r_sr = results.get(support_rdma_cmd)
            if r_sr and r_sr.exit_code == 0 and (r_sr.stdout or "").strip():
                support_rdma[device.device_num] = (r_sr.stdout or "").strip()
        return devices, qos_data, support_rdma

    def _collect_pensando_nic_structured(self, results: Dict[str, NicCommandResult]) -> Tuple[
        List[PensandoNicCard],
        List[PensandoNicDcqcn],
        List[PensandoNicEnvironment],
        List[PensandoNicLif],
        List[PensandoNicPcieAts],
        List[PensandoNicPort],
        List[PensandoNicQos],
        List[PensandoNicRdmaStatistics],
        Optional[PensandoNicVersionHostSoftware],
        List[PensandoNicVersionFirmware],
    ]:
        """Build Pensando NIC structured data from results using legacy text parsers."""

        def _stdout(cmd: str) -> str:
            r = results.get(cmd)
            return (r.stdout or "").strip() if r and r.exit_code == 0 else ""

        cards = self._parse_nicctl_card(_stdout("nicctl show card"))
        dcqcn_entries = self._parse_nicctl_dcqcn(_stdout("nicctl show dcqcn"))
        environment_entries = self._parse_nicctl_environment(_stdout("nicctl show environment"))
        lif_entries = self._parse_nicctl_lif(_stdout("nicctl show lif"))
        pcie_ats_entries = self._parse_nicctl_pcie_ats(_stdout("nicctl show pcie ats"))
        port_entries = self._parse_nicctl_port(_stdout("nicctl show port"))
        qos_entries = self._parse_nicctl_qos(_stdout("nicctl show qos"))
        rdma_statistics_entries = self._parse_nicctl_rdma_statistics(
            _stdout("nicctl show rdma statistics")
        )
        version_host_software = self._parse_nicctl_version_host_software(
            _stdout("nicctl show version host-software")
        )
        version_firmware_entries = self._parse_nicctl_version_firmware(
            _stdout("nicctl show version firmware")
        )

        return (
            cards,
            dcqcn_entries,
            environment_entries,
            lif_entries,
            pcie_ats_entries,
            port_entries,
            qos_entries,
            rdma_statistics_entries,
            version_host_software,
            version_firmware_entries,
        )

    # --- Legacy text parsers (human-readable niccli/nicctl output) ---

    def _parse_niccli_listdev(self, stdout: str) -> List[NicCliDevice]:
        """Parse niccli --list_devices output into NicCliDevice list."""
        devices: List[NicCliDevice] = []
        current_num: Optional[int] = None
        model = adapter_port = interface_name = mac_address = pci_address = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            num_match = re.match(r"^(\d+)\s*\)\s*(.*)", line)
            if num_match:
                if current_num is not None and model is not None:
                    devices.append(
                        NicCliDevice(
                            device_num=current_num,
                            model=model.strip() or None,
                            adapter_port=adapter_port,
                            interface_name=interface_name,
                            mac_address=mac_address,
                            pci_address=pci_address,
                        )
                    )
                current_num = int(num_match.group(1))
                rest = num_match.group(2).strip()
                if rest and "(" in rest and ")" in rest:
                    model = re.sub(r"\s*\([^)]+\)\s*$", "", rest).strip() or None
                    port_match = re.search(r"\(([^)]+)\)\s*$", rest)
                    adapter_port = port_match.group(1).strip() if port_match else None
                else:
                    model = rest or None
                    adapter_port = None
                interface_name = mac_address = pci_address = None
                continue
            if current_num is None:
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip().lower(), val.strip()
                if "interface" in key or "device interface" in key:
                    interface_name = val or None
                elif "mac" in key:
                    mac_address = val or None
                elif "pci" in key:
                    pci_address = val or None
        if current_num is not None and (
            model is not None or interface_name or mac_address or pci_address
        ):
            devices.append(
                NicCliDevice(
                    device_num=current_num,
                    model=model,
                    adapter_port=adapter_port,
                    interface_name=interface_name,
                    mac_address=mac_address,
                    pci_address=pci_address,
                )
            )
        return devices

    def _parse_niccli_qos(self, device_num: int, stdout: str) -> NicCliQos:
        """Parse niccli -dev X qos --ets --show output."""
        prio_map: Dict[int, int] = {}
        tc_bandwidth: List[int] = []
        tsa_map: Dict[int, str] = {}
        pfc_enabled: Optional[int] = None
        app_entries: List[NicCliQosAppEntry] = []
        tc_rate_limit: List[int] = []
        for line in stdout.splitlines():
            line = line.strip()
            if "PRIO_MAP:" in line or "PRIO_MAP" in line:
                for part in re.findall(r"(\d+):(\d+)", line):
                    prio_map[int(part[0])] = int(part[1])
            if "TC Bandwidth:" in line:
                tc_bandwidth = [int(x) for x in re.findall(r"(\d+)%", line)]
            if "TSA_MAP:" in line:
                for i, m in enumerate(re.findall(r"\d+:(\w+)", line)):
                    tsa_map[i] = m
            if "PFC enabled:" in line:
                m = re.search(r"PFC enabled:\s*(\d+)", line, re.I)
                if m:
                    pfc_enabled = int(m.group(1))
            if "APP#" in line:
                app_entries = _parse_niccli_qos_app_entries(stdout)
                break
            if "TC Rate Limit:" in line:
                tc_rate_limit = [int(x) for x in re.findall(r"(\d+)%", line)]
        return NicCliQos(
            device_num=device_num,
            raw_output=stdout,
            prio_map=prio_map,
            tc_bandwidth=tc_bandwidth,
            tsa_map=tsa_map,
            pfc_enabled=pfc_enabled,
            app_entries=app_entries,
            tc_rate_limit=tc_rate_limit,
        )

    def _parse_nicctl_card(self, stdout: str) -> List[PensandoNicCard]:
        """Parse nicctl show card (text table) into PensandoNicCard list."""
        cards: List[PensandoNicCard] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("-") or "PCIe BDF" in line or "Id " in line:
                continue
            parts = line.split()
            if (
                len(parts) >= 2
                and re.match(r"^[0-9a-f-]{36}$", parts[0])
                and re.match(r"^[0-9a-f:.]{12,}$", parts[1])
            ):
                card_id, pcie_bdf = parts[0], parts[1]
                asic = parts[2] if len(parts) > 2 and not parts[2].startswith("0") else None
                fw_partition = parts[3] if len(parts) > 3 and parts[3] in ("A", "B") else None
                serial_number = parts[4] if len(parts) > 4 else None
                cards.append(
                    PensandoNicCard(
                        id=card_id,
                        pcie_bdf=pcie_bdf,
                        asic=asic,
                        fw_partition=fw_partition,
                        serial_number=serial_number,
                    )
                )
        return cards

    def _parse_nicctl_dcqcn(self, stdout: str) -> List[PensandoNicDcqcn]:
        """Parse nicctl show dcqcn (text) into PensandoNicDcqcn list."""
        entries: List[PensandoNicDcqcn] = []
        nic_id = pcie_bdf = None
        lif_id = roce_device = dcqcn_profile_id = status = None
        for line in stdout.splitlines():
            if "NIC :" in line or "NIC:" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    lif_id = roce_device = dcqcn_profile_id = status = None
            if nic_id and "Lif id" in line and ":" in line:
                lif_id = line.split(":", 1)[1].strip()
            if nic_id and "ROCE device" in line and ":" in line:
                roce_device = line.split(":", 1)[1].strip()
            if nic_id and "DCQCN profile id" in line and ":" in line:
                dcqcn_profile_id = line.split(":", 1)[1].strip()
            if nic_id and "Status" in line and ":" in line:
                status = line.split(":", 1)[1].strip()
                entries.append(
                    PensandoNicDcqcn(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf or "",
                        lif_id=lif_id,
                        roce_device=roce_device,
                        dcqcn_profile_id=dcqcn_profile_id,
                        status=status,
                    )
                )
        return entries

    def _parse_nicctl_environment(self, stdout: str) -> List[PensandoNicEnvironment]:
        """Parse nicctl show environment (text) into PensandoNicEnvironment list."""
        entries: List[PensandoNicEnvironment] = []
        nic_id = pcie_bdf = None
        data: Dict[str, Optional[float]] = {}
        for line in stdout.splitlines():
            if "NIC :" in line or "NIC:" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    if nic_id and pcie_bdf:
                        entries.append(
                            PensandoNicEnvironment(
                                nic_id=nic_id,
                                pcie_bdf=pcie_bdf,
                                total_power_drawn=data.get("total_power_drawn"),
                                core_power=data.get("core_power"),
                                arm_power=data.get("arm_power"),
                                local_board_temperature=data.get("local_board_temperature"),
                                die_temperature=data.get("die_temperature"),
                                input_voltage=data.get("input_voltage"),
                                core_voltage=data.get("core_voltage"),
                                core_frequency=data.get("core_frequency"),
                                cpu_frequency=data.get("cpu_frequency"),
                                p4_stage_frequency=data.get("p4_stage_frequency"),
                            )
                        )
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    data = {}
            if nic_id and ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip().lower(), val.strip()
                try:
                    v = float(val)
                    if "total power" in key or "pin" in key:
                        data["total_power_drawn"] = v
                    elif "core power" in key or "pout1" in key:
                        data["core_power"] = v
                    elif "arm power" in key or "pout2" in key:
                        data["arm_power"] = v
                    elif "local board" in key:
                        data["local_board_temperature"] = v
                    elif "die temperature" in key:
                        data["die_temperature"] = v
                    elif "input voltage" in key:
                        data["input_voltage"] = v
                    elif "core voltage" in key:
                        data["core_voltage"] = v
                    elif "core frequency" in key:
                        data["core_frequency"] = v
                    elif "cpu frequency" in key:
                        data["cpu_frequency"] = v
                    elif "p4 stage" in key:
                        data["p4_stage_frequency"] = v
                except ValueError:
                    pass
        if nic_id and pcie_bdf:
            entries.append(
                PensandoNicEnvironment(
                    nic_id=nic_id,
                    pcie_bdf=pcie_bdf,
                    total_power_drawn=data.get("total_power_drawn"),
                    core_power=data.get("core_power"),
                    arm_power=data.get("arm_power"),
                    local_board_temperature=data.get("local_board_temperature"),
                    die_temperature=data.get("die_temperature"),
                    input_voltage=data.get("input_voltage"),
                    core_voltage=data.get("core_voltage"),
                    core_frequency=data.get("core_frequency"),
                    cpu_frequency=data.get("cpu_frequency"),
                    p4_stage_frequency=data.get("p4_stage_frequency"),
                )
            )
        return entries

    def _parse_nicctl_lif(self, stdout: str) -> List[PensandoNicLif]:
        """Parse nicctl show lif (text) into PensandoNicLif list."""
        entries: List[PensandoNicLif] = []
        nic_id = pcie_bdf = None
        for line in stdout.splitlines():
            if "NIC " in line and ":" in line and "(" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
            if "LIF :" in line or "Lif :" in line or "Lif:" in line:
                rest = line.split(":", 1)[-1].strip()
                lif_match = re.match(r"([0-9a-f-]{36})\s*\(([^)]*)\)", rest)
                if lif_match and nic_id:
                    lif_id, lif_name = lif_match.group(1), lif_match.group(2).strip()
                    entries.append(
                        PensandoNicLif(
                            nic_id=nic_id,
                            pcie_bdf=pcie_bdf or "",
                            lif_id=lif_id,
                            lif_name=lif_name or None,
                        )
                    )
                elif re.match(r"^[0-9a-f-]{36}$", rest.strip()) and nic_id:
                    entries.append(
                        PensandoNicLif(
                            nic_id=nic_id,
                            pcie_bdf=pcie_bdf or "",
                            lif_id=rest.strip(),
                            lif_name=None,
                        )
                    )
        return entries

    def _parse_nicctl_pcie_ats(self, stdout: str) -> List[PensandoNicPcieAts]:
        """Parse nicctl show pcie ats (text) into PensandoNicPcieAts list."""
        entries: List[PensandoNicPcieAts] = []
        for line in stdout.splitlines():
            m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)\s*:\s*(\w+)", line)
            if m:
                entries.append(
                    PensandoNicPcieAts(
                        nic_id=m.group(1).strip(),
                        pcie_bdf=m.group(2).strip(),
                        status=m.group(3).strip(),
                    )
                )
        return entries

    def _parse_nicctl_port(self, stdout: str) -> List[PensandoNicPort]:
        """Parse nicctl show port (text) into PensandoNicPort list."""
        entries: List[PensandoNicPort] = []
        nic_id = pcie_bdf = None
        port_id = port_name = None
        spec_speed = status_operational_status = None
        for line in stdout.splitlines():
            if "NIC " in line and ":" in line and "(" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    port_id = port_name = None
            if "Port :" in line or "Port:" in line:
                if nic_id and port_id is not None:
                    entries.append(
                        PensandoNicPort(
                            nic_id=nic_id,
                            pcie_bdf=pcie_bdf or "",
                            port_id=port_id,
                            port_name=port_name or port_id,
                            spec_speed=spec_speed,
                            status_operational_status=status_operational_status,
                        )
                    )
                rest = line.split(":", 1)[-1].strip()
                port_match = re.match(r"([0-9a-f-]{36})\s*\(([^)]+)\)", rest)
                if port_match:
                    port_id, port_name = port_match.group(1), port_match.group(2)
                else:
                    port_id = rest if re.match(r"^[0-9a-f-]{36}$", rest.strip()) else None
                    port_name = ""
                spec_speed = status_operational_status = None
            if (
                nic_id
                and "speed" in line
                and ":" in line
                and "Spec" not in line
                and "Advertised" not in line
            ):
                spec_speed = line.split(":", 1)[1].strip()
            if nic_id and "Operational status" in line and ":" in line:
                status_operational_status = line.split(":", 1)[1].strip()
        if nic_id and port_id is not None:
            entries.append(
                PensandoNicPort(
                    nic_id=nic_id,
                    pcie_bdf=pcie_bdf or "",
                    port_id=port_id,
                    port_name=port_name or port_id,
                    spec_speed=spec_speed,
                    status_operational_status=status_operational_status,
                )
            )
        return entries

    def _parse_nicctl_qos(self, stdout: str) -> List[PensandoNicQos]:
        """Parse nicctl show qos (text) into PensandoNicQos list."""
        entries: List[PensandoNicQos] = []
        nic_id = pcie_bdf = port_id = None
        classification_type = None
        scheduling: List[PensandoNicQosScheduling] = []
        for line in stdout.splitlines():
            if "NIC " in line and "(" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    port_id = None
                    scheduling = []
            if "Port :" in line:
                port_match = re.search(r"([0-9a-f-]{36})", line)
                port_id = port_match.group(1) if port_match else ""
            if "Classification type" in line and ":" in line:
                classification_type = line.split(":", 1)[1].strip()
            if "DWRR" in line or "Scheduling" in line:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        prio = int(parts[0])
                        sched_type = parts[1] if len(parts) > 1 else None
                        bw = int(parts[2]) if parts[2].isdigit() else None
                        rate = parts[3] if len(parts) > 3 else None
                        scheduling.append(
                            PensandoNicQosScheduling(
                                priority=prio,
                                scheduling_type=sched_type,
                                bandwidth=bw,
                                rate_limit=rate,
                            )
                        )
                    except (ValueError, IndexError):
                        pass
            if nic_id and port_id and (classification_type is not None or scheduling):
                entries.append(
                    PensandoNicQos(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf or "",
                        port_id=port_id,
                        classification_type=classification_type,
                        scheduling=scheduling,
                    )
                )
        return entries

    def _parse_nicctl_rdma_statistics(self, stdout: str) -> List[PensandoNicRdmaStatistics]:
        """Parse nicctl show rdma statistics (text) into PensandoNicRdmaStatistics list."""
        entries: List[PensandoNicRdmaStatistics] = []
        nic_id = pcie_bdf = None
        stats: List[PensandoNicRdmaStatistic] = []
        for line in stdout.splitlines():
            if "NIC :" in line or "NIC:" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    if nic_id and stats:
                        entries.append(
                            PensandoNicRdmaStatistics(
                                nic_id=nic_id,
                                pcie_bdf=pcie_bdf or "",
                                statistics=stats,
                            )
                        )
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    stats = []
            if nic_id and ":" in line and "NIC" not in line:
                key, _, val = line.partition(":")
                name, val = key.strip(), val.strip()
                try:
                    count = int(val)
                    stats.append(PensandoNicRdmaStatistic(name=name, count=count))
                except ValueError:
                    pass
        if nic_id and stats:
            entries.append(
                PensandoNicRdmaStatistics(
                    nic_id=nic_id,
                    pcie_bdf=pcie_bdf or "",
                    statistics=stats,
                )
            )
        return entries

    def _parse_nicctl_version_host_software(
        self, stdout: str
    ) -> Optional[PensandoNicVersionHostSoftware]:
        """Parse nicctl show version host-software (text)."""
        if not stdout or not stdout.strip():
            return None
        version = ipc_driver = ionic_driver = None
        for line in stdout.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip().lower(), val.strip()
                if "nicctl" in key:
                    version = val
                elif "ipc" in key:
                    ipc_driver = val
                elif "ionic" in key:
                    ionic_driver = val
        return PensandoNicVersionHostSoftware(
            version=version,
            ipc_driver=ipc_driver,
            ionic_driver=ionic_driver,
        )

    def _parse_nicctl_version_firmware(self, stdout: str) -> List[PensandoNicVersionFirmware]:
        """Parse nicctl show version firmware (text) into PensandoNicVersionFirmware list."""
        entries: List[PensandoNicVersionFirmware] = []
        nic_id = pcie_bdf = None
        cpld = boot0 = uboot_a = firmware_a = device_config_a = None
        for line in stdout.splitlines():
            if "NIC :" in line or "NIC:" in line:
                m = re.search(r"NIC\s*:\s*([^\s(]+)\s*\(([^)]+)\)", line)
                if m:
                    if nic_id:
                        entries.append(
                            PensandoNicVersionFirmware(
                                nic_id=nic_id,
                                pcie_bdf=pcie_bdf or "",
                                cpld=cpld,
                                boot0=boot0,
                                uboot_a=uboot_a,
                                firmware_a=firmware_a,
                                device_config_a=device_config_a,
                            )
                        )
                    nic_id, pcie_bdf = m.group(1).strip(), m.group(2).strip()
                    cpld = boot0 = uboot_a = firmware_a = device_config_a = None
            if nic_id and ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip().lower(), val.strip()
                if "cpld" in key:
                    cpld = val
                elif "boot0" in key:
                    boot0 = val
                elif "uboot-a" in key or "uboot_a" in key:
                    uboot_a = val
                elif "firmware-a" in key or "firmware_a" in key:
                    firmware_a = val
                elif "device config" in key or "device_config" in key:
                    device_config_a = val
        if nic_id:
            entries.append(
                PensandoNicVersionFirmware(
                    nic_id=nic_id,
                    pcie_bdf=pcie_bdf or "",
                    cpld=cpld,
                    boot0=boot0,
                    uboot_a=uboot_a,
                    firmware_a=firmware_a,
                    device_config_a=device_config_a,
                )
            )
        return entries
