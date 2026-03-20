# Plugin Documentation

# Plugin Table

| Plugin | Collection | Analyzer Args | Collection Args | DataModel | Collector | Analyzer |
| --- | --- | --- | --- | --- | --- | --- |
| AmdSmiPlugin | bad-pages<br>firmware --json<br>list --json<br>metric -g all<br>partition --json<br>process --json<br>ras --cper --folder={folder}<br>ras --afid --cper-file {cper_file}<br>static -g all --json<br>static -g {gpu_id} --json<br>topology<br>version --json<br>xgmi -l<br>xgmi -m | **Analyzer Args:**<br>- `check_static_data`: bool — If True, run static data checks (e.g. driver version, partition mode).<br>- `expected_gpu_processes`: Optional[int] — Expected number of GPU processes.<br>- `expected_max_power`: Optional[int] — Expected maximum power value (e.g. watts).<br>- `expected_driver_version`: Optional[str] — Expected AMD driver version string.<br>- `expected_memory_partition_mode`: Optional[str] — Expected memory partition mode (e.g. sp3, dp).<br>- `expected_compute_partition_mode`: Optional[str] — Expected compute partition mode.<br>- `expected_pldm_version`: Optional[str] — Expected PLDM version string.<br>- `l0_to_recovery_count_error_threshold`: Optional[int] — L0-to-recovery count above which an error is raised.<br>- `l0_to_recovery_count_warning_threshold`: Optional[int] — L0-to-recovery count above which a warning is raised.<br>- `vendorid_ep`: Optional[str] — Expected endpoint vendor ID (e.g. for PCIe).<br>- `vendorid_ep_vf`: Optional[str] — Expected endpoint VF vendor ID.<br>- `devid_ep`: Optional[str] — Expected endpoint device ID.<br>- `devid_ep_vf`: Optional[str] — Expected endpoint VF device ID.<br>- `sku_name`: Optional[str] — Expected SKU name string for GPU.<br>- `expected_xgmi_speed`: Optional[list[float]] — Expected xGMI speed value(s) (e.g. link rate).<br>- `analysis_range_start`: Optional[datetime.datetime] — Start of time range for time-windowed analysis.<br>- `analysis_range_end`: Optional[datetime.datetime] — End of time range for time-windowed analysis. | **Collection Args:**<br>- `cper_file_path`: Optional[str] — Path to CPER folder or file for RAS AFID collection (ras --afid --cper-file). | [AmdSmiDataModel](#AmdSmiDataModel-Model) | [AmdSmiCollector](#Collector-Class-AmdSmiCollector) | [AmdSmiAnalyzer](#Data-Analyzer-Class-AmdSmiAnalyzer) |
| BiosPlugin | sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'<br>wmic bios get SMBIOSBIOSVersion /Value | **Analyzer Args:**<br>- `exp_bios_version`: list[str] — Expected BIOS version(s) to match against collected value (str or list).<br>- `regex_match`: bool — If True, match exp_bios_version as regex; otherwise exact match. | - | [BiosDataModel](#BiosDataModel-Model) | [BiosCollector](#Collector-Class-BiosCollector) | [BiosAnalyzer](#Data-Analyzer-Class-BiosAnalyzer) |
| CmdlinePlugin | cat /proc/cmdline | **Analyzer Args:**<br>- `required_cmdline`: Union[str, List] — Command-line parameters that must be present (e.g. 'pci=bfsort').<br>- `banned_cmdline`: Union[str, List] — Command-line parameters that must not be present.<br>- `os_overrides`: Dict[str, nodescraper.plugins.inband.cmdline.cmdlineconfig.OverrideConfig] — Per-OS overrides for required_cmdline and banned_cmdline (keyed by OS identifier).<br>- `platform_overrides`: Dict[str, nodescraper.plugins.inband.cmdline.cmdlineconfig.OverrideConfig] — Per-platform overrides for required_cmdline and banned_cmdline (keyed by platform). | - | [CmdlineDataModel](#CmdlineDataModel-Model) | [CmdlineCollector](#Collector-Class-CmdlineCollector) | [CmdlineAnalyzer](#Data-Analyzer-Class-CmdlineAnalyzer) |
| DeviceEnumerationPlugin | powershell -Command "(Get-WmiObject -Class Win32_Processor &#124; Measure-Object).Count"<br>lspci -d {vendorid_ep}: &#124; grep -i 'VGA\&#124;Display\&#124;3D' &#124; wc -l<br>powershell -Command "(wmic path win32_VideoController get name &#124; findstr AMD &#124; Measure-Object).Count"<br>lscpu<br>lshw<br>lspci -d {vendorid_ep}: &#124; grep -i 'Virtual Function' &#124; wc -l<br>powershell -Command "(Get-VMHostPartitionableGpu &#124; Measure-Object).Count" | **Analyzer Args:**<br>- `cpu_count`: Optional[list[int]] — Expected CPU count(s); pass as int or list of ints. Analysis passes if actual is in list.<br>- `gpu_count`: Optional[list[int]] — Expected GPU count(s); pass as int or list of ints. Analysis passes if actual is in list.<br>- `vf_count`: Optional[list[int]] — Expected virtual function count(s); pass as int or list of ints. Analysis passes if actual is in list. | - | [DeviceEnumerationDataModel](#DeviceEnumerationDataModel-Model) | [DeviceEnumerationCollector](#Collector-Class-DeviceEnumerationCollector) | [DeviceEnumerationAnalyzer](#Data-Analyzer-Class-DeviceEnumerationAnalyzer) |
| DimmPlugin | sh -c 'dmidecode -t 17 &#124; tr -s " " &#124; grep -v "Volatile\&#124;None\&#124;Module" &#124; grep Size' 2>/dev/null<br>dmidecode<br>wmic memorychip get Capacity | - | **Collection Args:**<br>- `skip_sudo`: bool — If True, do not use sudo when running dmidecode or wmic for memory info. | [DimmDataModel](#DimmDataModel-Model) | [DimmCollector](#Collector-Class-DimmCollector) | - |
| DkmsPlugin | dkms status<br>dkms --version | **Analyzer Args:**<br>- `dkms_status`: Union[str, list] — Expected dkms status string(s) to match (e.g. 'amd/1.0.0'). At least one of dkms_status or dkms_version required.<br>- `dkms_version`: Union[str, list] — Expected dkms version string(s) to match. At least one of dkms_status or dkms_version required.<br>- `regex_match`: bool — If True, match dkms_status and dkms_version as regex; otherwise exact match. | - | [DkmsDataModel](#DkmsDataModel-Model) | [DkmsCollector](#Collector-Class-DkmsCollector) | [DkmsAnalyzer](#Data-Analyzer-Class-DkmsAnalyzer) |
| DmesgPlugin | dmesg --time-format iso -x<br>ls -1 /var/log/dmesg* 2>/dev/null &#124; grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' &#124;&#124; true | **Built-in Regexes:**<br>- Out of memory error: `(?:oom_kill_process.*)&#124;(?:Out of memory.*)`<br>- I/O Page Fault: `IO_PAGE_FAULT`<br>- Kernel Panic: `\bkernel panic\b.*`<br>- SQ Interrupt: `sq_intr`<br>- SRAM ECC: `sram_ecc.*`<br>- Failed to load driver. IP hardware init error.: `\[amdgpu\]\] \*ERROR\* hw_init of IP block.*`<br>- Failed to load driver. IP software init error.: `\[amdgpu\]\] \*ERROR\* sw_init of IP block.*`<br>- Real Time throttling activated: `sched: RT throttling activated.*`<br>- RCU preempt detected stalls: `rcu_preempt detected stalls.*`<br>- RCU preempt self-detected stall: `rcu_preempt self-detected stall.*`<br>- QCM fence timeout: `qcm fence wait loop timeout.*`<br>- General protection fault: `(?:[\w-]+(?:\[[0-9.]+\])?\s+)?general protectio...`<br>- Segmentation fault: `(?:segfault.*in .*\[)&#124;(?:[Ss]egmentation [Ff]au...`<br>- Failed to disallow cf state: `amdgpu: Failed to disallow cf state.*`<br>- Failed to terminate tmr: `\*ERROR\* Failed to terminate tmr.*`<br>- Suspend of IP block failed: `\*ERROR\* suspend of IP block <\w+> failed.*`<br>- amdgpu Page Fault: `(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:\s+\[\S...`<br>- Page Fault: `page fault for address.*`<br>- Fatal error during GPU init: `(?:amdgpu)(.*Fatal error during GPU init)&#124;(Fata...`<br>- PCIe AER Error Status: `(pcieport [\w:.]+: AER: aer_status:[^\n]*(?:\n[...`<br>- PCIe AER Correctable Error Status: `(.*aer_cor_status: 0x[0-9a-fA-F]+, aer_cor_mask...`<br>- PCIe AER Uncorrectable Error Status: `(.*aer_uncor_status: 0x[0-9a-fA-F]+, aer_uncor_...`<br>- PCIe AER Uncorrectable Error Severity with TLP Header: `(.*aer_uncor_severity: 0x[0-9a-fA-F]+.*)(\n.*TL...`<br>- Failed to read journal file: `Failed to read journal file.*`<br>- Journal file corrupted or uncleanly shut down: `journal corrupted or uncleanly shut down.*`<br>- ACPI BIOS Error: `ACPI BIOS Error`<br>- ACPI Error: `ACPI Error`<br>- Filesystem corrupted!: `EXT4-fs error \(device .*\):`<br>- Error in buffered IO, check filesystem integrity: `(Buffer I\/O error on dev)(?:ice)? (\w+)`<br>- PCIe card no longer present: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`<br>- PCIe Link Down: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`<br>- Mismatched clock configuration between PCIe device and host: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(curren...`<br>- RAS Correctable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Uncorrectable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Deferred Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Corrected PCIe Error: `((?:\[Hardware Error\]:\s+)?event severity: cor...`<br>- GPU Reset: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- GPU reset failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`<br>- ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`<br>- MCE Error: `\[Hardware Error\]:.+MC\d+_STATUS.*(?:\n.*){0,5}`<br>- Mode 2 Reset Failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)? (...`<br>- RAS Corrected Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- SGX Error: `x86/cpu: SGX disabled by BIOS`<br>- MMP Error: `Failed to load MMP firmware qat_4xxx_mmp.bin`<br>- GPU Throttled: `amdgpu \w{4}:\w{2}:\w{2}.\w: amdgpu: WARN: GPU ...`<br>- RAS Poison Consumed: `amdgpu[ 0-9a-fA-F:.]+:(?:\s*amdgpu:)?\s+(?:{\d+...`<br>- RAS Poison created: `amdgpu[ 0-9a-fA-F:.]+:(?:\s*amdgpu:)?\s+(?:{\d+...`<br>- Bad page threshold exceeded: `(amdgpu: Saved bad pages (\d+) reaches threshol...`<br>- RAS Hardware Error: `Hardware error from APEI Generic Hardware Error...`<br>- Error Address: `Error Address.*(?:\s.*)`<br>- RAS EDR Event: `EDR: EDR event received`<br>- DPC Event: `DPC: .*`<br>- LNet: ko2iblnd has no matching interfaces: `(?:\[[^\]]+\]\s*)?LNetError:.*ko2iblnd:\s*No ma...`<br>- LNet: Error starting up LNI: `(?:\[[^\]]+\]\s*)?LNetError:\s*.*Error\s*-?\d+\...`<br>- Lustre: network initialisation failed: `LustreError:.*ptlrpc_init_portals\(\).*network ...` | **Collection Args:**<br>- `collect_rotated_logs`: bool — If True, also collect rotated dmesg log files from /var/log/dmesg*.<br>- `skip_sudo`: bool — If True, do not use sudo when running dmesg or listing log files.<br>- `log_dmesg_data`: bool — If True, log the collected dmesg output in artifacts. | [DmesgData](#DmesgData-Model) | [DmesgCollector](#Collector-Class-DmesgCollector) | [DmesgAnalyzer](#Data-Analyzer-Class-DmesgAnalyzer) |
| FabricsPlugin | lspci &#124; grep -i cassini<br>lsmod &#124; grep cxi<br>cxi_stat<br>ibstat<br>ibv_devinfo<br>ls -l /sys/class/infiniband/*/device/net<br>fi_info -p cxi<br>mst start<br>mst status -v<br>ip link show<br>ofed_info -s | - | - | [FabricsDataModel](#FabricsDataModel-Model) | [FabricsCollector](#Collector-Class-FabricsCollector) | - |
| JournalPlugin | journalctl --no-pager --system --output=short-iso<br>journalctl --no-pager --system --output=json | **Analyzer Args:**<br>- `analysis_range_start`: Optional[datetime.datetime] — Start of time range for analysis (ISO format). Only events on or after this time are analyzed.<br>- `analysis_range_end`: Optional[datetime.datetime] — End of time range for analysis (ISO format). Only events before this time are analyzed.<br>- `check_priority`: Optional[int] — Check against journal log priority (0=emergency..7=debug). If an entry has priority <= check_priority, an ERROR event...<br>- `group`: bool — If True, group entries that have the same priority and message. | **Collection Args:**<br>- `boot`: Optional[int] — Optional boot ID to limit journal collection to a specific boot. | [JournalData](#JournalData-Model) | [JournalCollector](#Collector-Class-JournalCollector) | [JournalAnalyzer](#Data-Analyzer-Class-JournalAnalyzer) |
| KernelPlugin | sh -c 'uname -a'<br>sh -c 'cat /proc/sys/kernel/numa_balancing'<br>wmic os get Version /Value | **Analyzer Args:**<br>- `exp_kernel`: Union[str, list] — Expected kernel version string(s) to match (e.g. from uname -a).<br>- `exp_numa`: Optional[int] — Expected value for kernel.numa_balancing (e.g. 0 or 1).<br>- `regex_match`: bool — If True, match exp_kernel as regex; otherwise exact match. | - | [KernelDataModel](#KernelDataModel-Model) | [KernelCollector](#Collector-Class-KernelCollector) | [KernelAnalyzer](#Data-Analyzer-Class-KernelAnalyzer) |
| KernelModulePlugin | cat /proc/modules<br>modinfo amdgpu<br>wmic os get Version /Value | **Analyzer Args:**<br>- `kernel_modules`: dict[str, dict] — Expected kernel module name -> {version, etc.}. Analyzer checks collected modules match.<br>- `regex_filter`: list[str] — List of regex patterns to filter which collected modules are checked (default: amd). | - | [KernelModuleDataModel](#KernelModuleDataModel-Model) | [KernelModuleCollector](#Collector-Class-KernelModuleCollector) | [KernelModuleAnalyzer](#Data-Analyzer-Class-KernelModuleAnalyzer) |
| MemoryPlugin | free -b<br>lsmem<br>numactl -H<br>wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value | **Analyzer Args:**<br>- `ratio`: float — Required free-memory ratio (0-1). Analysis fails if free/total < ratio.<br>- `memory_threshold`: str — Minimum free memory required (e.g. '30Gi', '1T'). Used when ratio is not sufficient. | - | [MemoryDataModel](#MemoryDataModel-Model) | [MemoryCollector](#Collector-Class-MemoryCollector) | [MemoryAnalyzer](#Data-Analyzer-Class-MemoryAnalyzer) |
| NetworkPlugin | ip addr show<br>curl<br>ethtool -S {interface}<br>ethtool {interface}<br>lldpcli show neighbor<br>lldpctl<br>ip neighbor show<br>ping<br>ip route show<br>ip rule show<br>wget | - | **Collection Args:**<br>- `url`: Optional[str] — Optional URL to probe for network connectivity (used with netprobe).<br>- `netprobe`: Optional[Literal['ping', 'wget', 'curl']] — Tool to use for network connectivity probe: ping, wget, or curl. | [NetworkDataModel](#NetworkDataModel-Model) | [NetworkCollector](#Collector-Class-NetworkCollector) | - |
| NicPlugin | niccli --listdev<br>niccli --list<br>niccli --list_devices<br>niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering<br>niccli --dev {device_num} nvm --getoption pcie_relaxed_ordering<br>niccli -dev {device_num} nvm -getoption performance_profile<br>niccli --dev {device_num} nvm --getoption performance_profile<br>niccli -dev {device_num} nvm -getoption support_rdma -scope 0<br>niccli -dev {device_num} getqos<br>niccli --dev {device_num} nvm --getoption support_rdma<br>niccli --dev {device_num} qos --ets --show<br>niccli --version<br>nicctl show card<br>nicctl --version<br>nicctl show card flash partition --json<br>nicctl show card interrupts --json<br>nicctl show card logs --non-persistent<br>nicctl show card logs --boot-fault<br>nicctl show card logs --persistent<br>nicctl show card profile --json<br>nicctl show card time --json<br>nicctl show card statistics packet-buffer summary --json<br>nicctl show lif statistics --json<br>nicctl show lif internal queue-to-ud-pinning<br>nicctl show pipeline internal anomalies<br>nicctl show pipeline internal rsq-ring<br>nicctl show pipeline internal statistics memory<br>nicctl show port fsm<br>nicctl show port transceiver --json<br>nicctl show port statistics --json<br>nicctl show port internal mac<br>nicctl show qos headroom --json<br>nicctl show rdma queue --json<br>nicctl show rdma queue-pair --detail --json<br>nicctl show version firmware<br>nicctl show dcqcn<br>nicctl show environment<br>nicctl show lif<br>nicctl show pcie ats<br>nicctl show port<br>nicctl show qos<br>nicctl show rdma statistics<br>nicctl show version host-software<br>nicctl show dcqcn --card {card_id} --json<br>nicctl show card hardware-config --card {card_id} | **Analyzer Args:**<br>- `expected_values`: Optional[Dict[str, Dict[str, Any]]] — Per-command expected checks keyed by canonical key (see command_to_canonical_key).<br>- `performance_profile_expected`: str — Expected Broadcom performance_profile value (case-insensitive). Default RoCE.<br>- `support_rdma_disabled_values`: List[str] — Values that indicate RDMA is not supported (case-insensitive).<br>- `pcie_relaxed_ordering_expected`: str — Expected Broadcom pcie_relaxed_ordering value (e.g. 'Relaxed ordering = enabled'); checked case-insensitively. Defaul...<br>- `expected_qos_prio_map`: Optional[Dict[Any, Any]] — Expected priority-to-TC map (e.g. {0: 0, 1: 1}; keys may be int or str in config). Checked per device when set.<br>- `expected_qos_pfc_enabled`: Optional[int] — Expected PFC enabled value (0/1 or bitmask). Checked per device when set.<br>- `expected_qos_tsa_map`: Optional[Dict[Any, Any]] — Expected TSA map for ETS (e.g. {0: 'ets', 1: 'strict'}; keys may be int or str in config). Checked per device when set.<br>- `expected_qos_tc_bandwidth`: Optional[List[int]] — Expected TC bandwidth percentages. Checked per device when set.<br>- `require_qos_consistent_across_adapters`: bool — When True and no expected_qos_* are set, require all adapters to have the same prio_map, pfc_enabled, and tsa_map.<br>- `nicctl_log_error_regex`: Optional[List[Dict[str, Any]]] — Optional list of error patterns for nicctl show card logs. | **Collection Args:**<br>- `commands`: Optional[List[str]] — Optional list of niccli/nicctl commands to run. When None, default command set is used.<br>- `use_sudo_niccli`: bool — If True, run niccli commands with sudo when required.<br>- `use_sudo_nicctl`: bool — If True, run nicctl commands with sudo when required. | [NicDataModel](#NicDataModel-Model) | [NicCollector](#Collector-Class-NicCollector) | [NicAnalyzer](#Data-Analyzer-Class-NicAnalyzer) |
| NvmePlugin | nvme smart-log {dev}<br>nvme error-log {dev} --log-entries=256<br>nvme id-ctrl {dev}<br>nvme id-ns {dev}{ns}<br>nvme fw-log {dev}<br>nvme self-test-log {dev}<br>nvme get-log {dev} --log-id=6 --log-len=512<br>nvme telemetry-log {dev} --output-file={dev}_{f_name}<br>nvme list -o json | - | - | [NvmeDataModel](#NvmeDataModel-Model) | [NvmeCollector](#Collector-Class-NvmeCollector) | - |
| OsPlugin | sh -c '( lsb_release -ds &#124;&#124; (cat /etc/*release &#124; grep PRETTY_NAME) &#124;&#124; uname -om ) 2>/dev/null &#124; head -n1'<br>cat /etc/*release &#124; grep VERSION_ID<br>wmic os get Version /value<br>wmic os get Caption /Value | **Analyzer Args:**<br>- `exp_os`: Union[str, list] — Expected OS name/version string(s) to match (e.g. from lsb_release or /etc/os-release).<br>- `exact_match`: bool — If True, require exact match for exp_os; otherwise substring match. | - | [OsDataModel](#OsDataModel-Model) | [OsCollector](#Collector-Class-OsCollector) | [OsAnalyzer](#Data-Analyzer-Class-OsAnalyzer) |
| PackagePlugin | dnf list --installed<br>dpkg-query -W<br>pacman -Q<br>cat /etc/*release<br>wmic product get name,version | **Analyzer Args:**<br>- `exp_package_ver`: Dict[str, Optional[str]] — Map package name -> expected version (None = any version). Checked against installed packages.<br>- `regex_match`: bool — If True, match package versions with regex; otherwise exact or prefix match.<br>- `rocm_regex`: Optional[str] — Optional regex to identify ROCm package version (used when enable_rocm_regex is True).<br>- `enable_rocm_regex`: bool — If True, use rocm_regex (or default pattern) to extract ROCm version for checks. | - | [PackageDataModel](#PackageDataModel-Model) | [PackageCollector](#Collector-Class-PackageCollector) | [PackageAnalyzer](#Data-Analyzer-Class-PackageAnalyzer) |
| PciePlugin | lspci -d {vendor_id}: -nn<br>lspci -x<br>lspci -xxxx<br>lspci -PP<br>lspci -PP -d {vendor_id}:{dev_id}<br>lspci -vvv<br>lspci -vvvt | **Analyzer Args:**<br>- `exp_speed`: int — Expected PCIe link speed (generation 1–5).<br>- `exp_width`: int — Expected PCIe link width in lanes (1–16).<br>- `exp_sriov_count`: int — Expected SR-IOV virtual function count.<br>- `exp_gpu_count_override`: Optional[int] — Override expected GPU count for validation.<br>- `exp_max_payload_size`: Union[Dict[int, int], int, NoneType] — Expected max payload size: int for all devices, or dict keyed by device ID.<br>- `exp_max_rd_req_size`: Union[Dict[int, int], int, NoneType] — Expected max read request size: int for all devices, or dict keyed by device ID.<br>- `exp_ten_bit_tag_req_en`: Union[Dict[int, int], int, NoneType] — Expected 10-bit tag request enable: int for all devices, or dict keyed by device ID. | - | [PcieDataModel](#PcieDataModel-Model) | [PcieCollector](#Collector-Class-PcieCollector) | [PcieAnalyzer](#Data-Analyzer-Class-PcieAnalyzer) |
| ProcessPlugin | top -b -n 1<br>rocm-smi --showpids<br>top -b -n 1 -o %CPU  | **Analyzer Args:**<br>- `max_kfd_processes`: int — Maximum allowed number of KFD (Kernel Fusion Driver) processes; 0 disables the check.<br>- `max_cpu_usage`: float — Maximum allowed CPU usage (percent) for process checks. | **Collection Args:**<br>- `top_n_process`: int — Number of top processes by CPU usage to collect (e.g. for top -b -n 1 -o %CPU). | [ProcessDataModel](#ProcessDataModel-Model) | [ProcessCollector](#Collector-Class-ProcessCollector) | [ProcessAnalyzer](#Data-Analyzer-Class-ProcessAnalyzer) |
| RdmaPlugin | rdma link -j<br>rdma dev<br>rdma link<br>rdma statistic -j | - | - | [RdmaDataModel](#RdmaDataModel-Model) | [RdmaCollector](#Collector-Class-RdmaCollector) | [RdmaAnalyzer](#Data-Analyzer-Class-RdmaAnalyzer) |
| RocmPlugin | {rocm_path}/opencl/bin/*/clinfo<br>env &#124; grep -Ei 'rocm&#124;hsa&#124;hip&#124;mpi&#124;openmp&#124;ucx&#124;miopen'<br>ls /sys/class/kfd/kfd/proc/<br>grep -i -E 'rocm' /etc/ld.so.conf.d/*<br>{rocm_path}/bin/rocminfo<br>ls -v -d {rocm_path}*<br>ls -v -d {rocm_path}-[3-7]* &#124; tail -1<br>ldconfig -p &#124; grep -i -E 'rocm'<br>grep . -r {rocm_path}/.info/* | **Analyzer Args:**<br>- `exp_rocm`: Union[str, list] — Expected ROCm version string(s) to match (e.g. from rocminfo).<br>- `exp_rocm_latest`: str — Expected 'latest' ROCm path or version string for versioned installs.<br>- `exp_rocm_sub_versions`: dict[str, Union[str, list]] — Map sub-version name (e.g. version_rocm) to expected string or list of allowed strings. | **Collection Args:**<br>- `rocm_path`: str — Base path to ROCm installation (e.g. /opt/rocm). Used for rocminfo, clinfo, and version discovery. | [RocmDataModel](#RocmDataModel-Model) | [RocmCollector](#Collector-Class-RocmCollector) | [RocmAnalyzer](#Data-Analyzer-Class-RocmAnalyzer) |
| StoragePlugin | sh -c 'df -lH -B1 &#124; grep -v 'boot''<br>wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace | - | **Collection Args:**<br>- `skip_sudo`: bool — If True, do not use sudo when running df and related storage commands. | [StorageDataModel](#StorageDataModel-Model) | [StorageCollector](#Collector-Class-StorageCollector) | [StorageAnalyzer](#Data-Analyzer-Class-StorageAnalyzer) |
| SysSettingsPlugin | cat /sys/{}<br>ls -1 /sys/{}<br>ls -l /sys/{} | **Analyzer Args:**<br>- `checks`: Optional[list[nodescraper.plugins.inband.sys_settings.analyzer_args.SysfsCheck]] — List of sysfs checks (path, expected values or pattern, display name). | **Collection Args:**<br>- `paths`: list[str] — Sysfs paths to read (cat). Paths with '*' are collected with ls -l (e.g. class/net/*/device).<br>- `directory_paths`: list[str] — Sysfs paths to list (ls -1); used for checks that match entry names by regex. | [SysSettingsDataModel](#SysSettingsDataModel-Model) | [SysSettingsCollector](#Collector-Class-SysSettingsCollector) | [SysSettingsAnalyzer](#Data-Analyzer-Class-SysSettingsAnalyzer) |
| SysctlPlugin | sysctl -n | **Analyzer Args:**<br>- `exp_vm_swappiness`: Optional[int] — Expected vm.swappiness value.<br>- `exp_vm_numa_balancing`: Optional[int] — Expected vm.numa_balancing value.<br>- `exp_vm_oom_kill_allocating_task`: Optional[int] — Expected vm.oom_kill_allocating_task value.<br>- `exp_vm_compaction_proactiveness`: Optional[int] — Expected vm.compaction_proactiveness value.<br>- `exp_vm_compact_unevictable_allowed`: Optional[int] — Expected vm.compact_unevictable_allowed value.<br>- `exp_vm_extfrag_threshold`: Optional[int] — Expected vm.extfrag_threshold value.<br>- `exp_vm_zone_reclaim_mode`: Optional[int] — Expected vm.zone_reclaim_mode value.<br>- `exp_vm_dirty_background_ratio`: Optional[int] — Expected vm.dirty_background_ratio value.<br>- `exp_vm_dirty_ratio`: Optional[int] — Expected vm.dirty_ratio value.<br>- `exp_vm_dirty_writeback_centisecs`: Optional[int] — Expected vm.dirty_writeback_centisecs value.<br>- `exp_kernel_numa_balancing`: Optional[int] — Expected kernel.numa_balancing value. | - | [SysctlDataModel](#SysctlDataModel-Model) | [SysctlCollector](#Collector-Class-SysctlCollector) | [SysctlAnalyzer](#Data-Analyzer-Class-SysctlAnalyzer) |
| SyslogPlugin | ls -1 /var/log/syslog* 2>/dev/null &#124; grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' &#124;&#124; true | - | - | [SyslogData](#SyslogData-Model) | [SyslogCollector](#Collector-Class-SyslogCollector) | - |
| UptimePlugin | uptime | - | - | [UptimeDataModel](#UptimeDataModel-Model) | [UptimeCollector](#Collector-Class-UptimeCollector) | - |

# Collectors

## Collector Class AmdSmiCollector

### Description

Class for collection of inband tool amd-smi data.

**Bases**: ['InBandDataCollector']

**Link to code**: [amdsmi_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/amdsmi/amdsmi_collector.py)

### Class Variables

- **AMD_SMI_EXE**: `amd-smi`
- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_VERSION**: `version --json`
- **CMD_LIST**: `list --json`
- **CMD_PROCESS**: `process --json`
- **CMD_PARTITION**: `partition --json`
- **CMD_FIRMWARE**: `firmware --json`
- **CMD_STATIC**: `static -g all --json`
- **CMD_STATIC_GPU**: `static -g {gpu_id} --json`
- **CMD_TOPOLOGY**: `topology`
- **CMD_METRIC**: `metric -g all`
- **CMD_BAD_PAGES**: `bad-pages`
- **CMD_XGMI_METRIC**: `xgmi -m`
- **CMD_XGMI_LINK**: `xgmi -l`
- **CMD_RAS**: `ras --cper --folder={folder}`
- **CMD_RAS_AFID**: `ras --afid --cper-file {cper_file}`

### Provides Data

AmdSmiDataModel

### Commands

- bad-pages
- firmware --json
- list --json
- metric -g all
- partition --json
- process --json
- ras --cper --folder={folder}
- ras --afid --cper-file {cper_file}
- static -g all --json
- static -g {gpu_id} --json
- topology
- version --json
- xgmi -l
- xgmi -m

## Collector Class BiosCollector

### Description

Collect BIOS details

**Bases**: ['InBandDataCollector']

**Link to code**: [bios_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/bios/bios_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic bios get SMBIOSBIOSVersion /Value`
- **CMD**: `sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'`

### Provides Data

BiosDataModel

### Commands

- sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'
- wmic bios get SMBIOSBIOSVersion /Value

## Collector Class CmdlineCollector

### Description

Read linux cmdline data

**Bases**: ['InBandDataCollector']

**Link to code**: [cmdline_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/cmdline/cmdline_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `cat /proc/cmdline`

### Provides Data

CmdlineDataModel

### Commands

- cat /proc/cmdline

## Collector Class DeviceEnumerationCollector

### Description

Collect CPU and GPU count

**Bases**: ['InBandDataCollector']

**Link to code**: [device_enumeration_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/device_enumeration/device_enumeration_collector.py)

### Class Variables

- **CMD_GPU_COUNT_LINUX**: `lspci -d {vendorid_ep}: | grep -i 'VGA\|Display\|3D' | wc -l`
- **CMD_VF_COUNT_LINUX**: `lspci -d {vendorid_ep}: | grep -i 'Virtual Function' | wc -l`
- **CMD_LSCPU_LINUX**: `lscpu`
- **CMD_LSHW_LINUX**: `lshw`
- **CMD_CPU_COUNT_WINDOWS**: `powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"`
- **CMD_GPU_COUNT_WINDOWS**: `powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"`
- **CMD_VF_COUNT_WINDOWS**: `powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"`

### Provides Data

DeviceEnumerationDataModel

### Commands

- powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"
- lspci -d {vendorid_ep}: | grep -i 'VGA\|Display\|3D' | wc -l
- powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"
- lscpu
- lshw
- lspci -d {vendorid_ep}: | grep -i 'Virtual Function' | wc -l
- powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"

## Collector Class DimmCollector

### Description

Collect data on installed DIMMs

**Bases**: ['InBandDataCollector']

**Link to code**: [dimm_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dimm/dimm_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic memorychip get Capacity`
- **CMD**: `sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\|None\|Module" | grep Size' 2>/dev/null`
- **CMD_DMIDECODE_FULL**: `dmidecode`

### Provides Data

DimmDataModel

### Commands

- sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\|None\|Module" | grep Size' 2>/dev/null
- dmidecode
- wmic memorychip get Capacity

## Collector Class DkmsCollector

### Description

Collect DKMS status and version data

**Bases**: ['InBandDataCollector']

**Link to code**: [dkms_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dkms/dkms_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_STATUS**: `dkms status`
- **CMD_VERSION**: `dkms --version`

### Provides Data

DkmsDataModel

### Commands

- dkms status
- dkms --version

## Collector Class DmesgCollector

### Description

Read dmesg log

**Bases**: ['InBandDataCollector']

**Link to code**: [dmesg_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dmesg/dmesg_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `dmesg --time-format iso -x`
- **CMD_LOGS**: `ls -1 /var/log/dmesg* 2>/dev/null | grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' || true`

### Provides Data

DmesgData

### Commands

- dmesg --time-format iso -x
- ls -1 /var/log/dmesg* 2>/dev/null | grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' || true

## Collector Class FabricsCollector

### Description

Collect InfiniBand/RDMA fabrics configuration details

**Bases**: ['InBandDataCollector']

**Link to code**: [fabrics_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/fabrics/fabrics_collector.py)

### Class Variables

- **CMD_IBSTAT**: `ibstat`
- **CMD_IBV_DEVINFO**: `ibv_devinfo`
- **CMD_IB_DEV_NETDEVS**: `ls -l /sys/class/infiniband/*/device/net`
- **CMD_OFED_INFO**: `ofed_info -s`
- **CMD_MST_START**: `mst start`
- **CMD_MST_STATUS**: `mst status -v`
- **CMD_CASSINI_PCI**: `lspci | grep -i cassini`
- **CMD_NET_LINK**: `ip link show`
- **CMD_LIBFABRIC_INFO**: `fi_info -p cxi`
- **CMD_CXI_STAT**: `cxi_stat`
- **CMD_CXI_MODULES**: `lsmod | grep cxi`

### Provides Data

FabricsDataModel

### Commands

- lspci | grep -i cassini
- lsmod | grep cxi
- cxi_stat
- ibstat
- ibv_devinfo
- ls -l /sys/class/infiniband/*/device/net
- fi_info -p cxi
- mst start
- mst status -v
- ip link show
- ofed_info -s

## Collector Class JournalCollector

### Description

Read journal log via journalctl.

**Bases**: ['InBandDataCollector']

**Link to code**: [journal_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/journal_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `journalctl --no-pager --system --output=short-iso`
- **CMD_JSON**: `journalctl --no-pager --system --output=json`

### Provides Data

JournalData

### Commands

- journalctl --no-pager --system --output=short-iso
- journalctl --no-pager --system --output=json

## Collector Class KernelCollector

### Description

Read kernel version

**Bases**: ['InBandDataCollector']

**Link to code**: [kernel_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/kernel_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic os get Version /Value`
- **CMD**: `sh -c 'uname -a'`
- **CMD_NUMA_BALANCING**: `sh -c 'cat /proc/sys/kernel/numa_balancing'`

### Provides Data

KernelDataModel

### Commands

- sh -c 'uname -a'
- sh -c 'cat /proc/sys/kernel/numa_balancing'
- wmic os get Version /Value

## Collector Class KernelModuleCollector

### Description

Read kernel modules and associated parameters

**Bases**: ['InBandDataCollector']

**Link to code**: [kernel_module_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/kernel_module_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic os get Version /Value`
- **CMD**: `cat /proc/modules`
- **CMD_MODINFO_AMDGPU**: `modinfo amdgpu`

### Provides Data

KernelModuleDataModel

### Commands

- cat /proc/modules
- modinfo amdgpu
- wmic os get Version /Value

## Collector Class MemoryCollector

### Description

Collect memory usage details

**Bases**: ['InBandDataCollector']

**Link to code**: [memory_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/memory_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value`
- **CMD**: `free -b`
- **CMD_LSMEM**: `lsmem`
- **CMD_NUMACTL**: `numactl -H`

### Provides Data

MemoryDataModel

### Commands

- free -b
- lsmem
- numactl -H
- wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value

## Collector Class NetworkCollector

### Description

Collect network configuration details using ip command

**Bases**: ['InBandDataCollector']

**Link to code**: [network_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/network/network_collector.py)

### Class Variables

- **CMD_ADDR**: `ip addr show`
- **CMD_ROUTE**: `ip route show`
- **CMD_RULE**: `ip rule show`
- **CMD_NEIGHBOR**: `ip neighbor show`
- **CMD_ETHTOOL_TEMPLATE**: `ethtool {interface}`
- **CMD_ETHTOOL_S_TEMPLATE**: `ethtool -S {interface}`
- **CMD_PING**: `ping`
- **CMD_WGET**: `wget`
- **CMD_CURL**: `curl`
- **CMD_LLDPCLI_NEIGHBOR**: `lldpcli show neighbor`
- **CMD_LLDPCTL**: `lldpctl`

### Provides Data

NetworkDataModel

### Commands

- ip addr show
- curl
- ethtool -S {interface}
- ethtool {interface}
- lldpcli show neighbor
- lldpctl
- ip neighbor show
- ping
- ip route show
- ip rule show
- wget

## Collector Class NicCollector

### Description

Collect raw output from niccli (Broadcom) and nicctl (Pensando) commands.

**Bases**: ['InBandDataCollector']

**Link to code**: [nic_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nic/nic_collector.py)

### Class Variables

- **CMD_NICCLI_VERSION**: `niccli --version`
- **CMD_NICCLI_LIST**: `niccli --list`
- **CMD_NICCLI_LIST_DEVICES**: `niccli --list_devices`
- **CMD_NICCLI_LIST_DEVICES_LEGACY**: `niccli --listdev`
- **CMD_NICCLI_DISCOVERY_LEGACY**: `['niccli --listdev', 'niccli --list']`
- **CMD_NICCLI_DISCOVERY_NEW**: `['niccli --list_devices', 'niccli --list']`
- **CMD_NICCLI_DISCOVERY**: `['niccli --listdev', 'niccli --list']`
- **CMD_NICCLI_DISCOVERY_ALL**: `frozenset({'niccli --list_devices', 'niccli --list', 'niccli --listdev'})`
- **CMD_NICCLI_SUPPORT_RDMA_TEMPLATE_LEGACY**: `niccli -dev {device_num} nvm -getoption support_rdma -scope 0`
- **CMD_NICCLI_PERFORMANCE_PROFILE_TEMPLATE_LEGACY**: `niccli -dev {device_num} nvm -getoption performance_profile`
- **CMD_NICCLI_PCIE_RELAXED_ORDERING_TEMPLATE_LEGACY**: `niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering`
- **CMD_NICCLI_QOS_TEMPLATE_LEGACY**: `niccli -dev {device_num} getqos`
- **CMD_NICCLI_PER_DEVICE_LEGACY**: `[
  niccli -dev {device_num} nvm -getoption support_rdma -scope 0,
  niccli -dev {device_num} nvm -getoption performance_profile,
  niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering,
  niccli -dev {device_num} getqos
]`
- **CMD_NICCLI_SUPPORT_RDMA_TEMPLATE_NEW**: `niccli --dev {device_num} nvm --getoption support_rdma`
- **CMD_NICCLI_PERFORMANCE_PROFILE_TEMPLATE_NEW**: `niccli --dev {device_num} nvm --getoption performance_profile`
- **CMD_NICCLI_PCIE_RELAXED_ORDERING_TEMPLATE_NEW**: `niccli --dev {device_num} nvm --getoption pcie_relaxed_ordering`
- **CMD_NICCLI_QOS_TEMPLATE_NEW**: `niccli --dev {device_num} qos --ets --show`
- **CMD_NICCLI_PER_DEVICE_NEW**: `[
  niccli --dev {device_num} nvm --getoption support_rdma,
  niccli --dev {device_num} nvm --getoption performance_profile,
  niccli --dev {device_num} nvm --getoption pcie_relaxed_ordering,
  niccli --dev {device_num} qos --ets --show
]`
- **CMD_NICCLI_SUPPORT_RDMA_TEMPLATE**: `niccli -dev {device_num} nvm -getoption support_rdma -scope 0`
- **CMD_NICCLI_PERFORMANCE_PROFILE_TEMPLATE**: `niccli -dev {device_num} nvm -getoption performance_profile`
- **CMD_NICCLI_PCIE_RELAXED_ORDERING_TEMPLATE**: `niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering`
- **CMD_NICCLI_PER_DEVICE**: `[
  niccli -dev {device_num} nvm -getoption support_rdma -scope 0,
  niccli -dev {device_num} nvm -getoption performance_profile,
  niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering,
  niccli -dev {device_num} getqos
]`
- **CMD_NICCTL_CARD_TEXT**: `nicctl show card`
- **CMD_NICCTL_GLOBAL**: `[
  nicctl --version,
  nicctl show card flash partition --json,
  nicctl show card interrupts --json,
  nicctl show card logs --non-persistent,
  nicctl show card logs --boot-fault,
  nicctl show card logs --persistent,
  nicctl show card profile --json,
  nicctl show card time --json,
  nicctl show card statistics packet-buffer summary --json,
  nicctl show lif statistics --json,
  nicctl show lif internal queue-to-ud-pinning,
  nicctl show pipeline internal anomalies,
  nicctl show pipeline internal rsq-ring,
  nicctl show pipeline internal statistics memory,
  nicctl show port fsm,
  nicctl show port transceiver --json,
  nicctl show port statistics --json,
  nicctl show port internal mac,
  nicctl show qos headroom --json,
  nicctl show rdma queue --json,
  nicctl show rdma queue-pair --detail --json,
  nicctl show version firmware
]`
- **CMD_NICCTL_PER_CARD**: `['nicctl show dcqcn --card {card_id} --json', 'nicctl show card hardware-config --card {card_id}']`
- **CMD_NICCTL_LEGACY_TEXT**: `[
  nicctl show card,
  nicctl show dcqcn,
  nicctl show environment,
  nicctl show lif,
  nicctl show pcie ats,
  nicctl show port,
  nicctl show qos,
  nicctl show rdma statistics,
  nicctl show version host-software
]`

### Provides Data

NicDataModel

### Commands

- niccli --listdev
- niccli --list
- niccli --list_devices
- niccli -dev {device_num} nvm -getoption pcie_relaxed_ordering
- niccli --dev {device_num} nvm --getoption pcie_relaxed_ordering
- niccli -dev {device_num} nvm -getoption performance_profile
- niccli --dev {device_num} nvm --getoption performance_profile
- niccli -dev {device_num} nvm -getoption support_rdma -scope 0
- niccli -dev {device_num} getqos
- niccli --dev {device_num} nvm --getoption support_rdma
- niccli --dev {device_num} qos --ets --show
- niccli --version
- nicctl show card
- nicctl --version
- nicctl show card flash partition --json
- nicctl show card interrupts --json
- nicctl show card logs --non-persistent
- nicctl show card logs --boot-fault
- nicctl show card logs --persistent
- nicctl show card profile --json
- nicctl show card time --json
- nicctl show card statistics packet-buffer summary --json
- nicctl show lif statistics --json
- nicctl show lif internal queue-to-ud-pinning
- nicctl show pipeline internal anomalies
- nicctl show pipeline internal rsq-ring
- nicctl show pipeline internal statistics memory
- nicctl show port fsm
- nicctl show port transceiver --json
- nicctl show port statistics --json
- nicctl show port internal mac
- nicctl show qos headroom --json
- nicctl show rdma queue --json
- nicctl show rdma queue-pair --detail --json
- nicctl show version firmware
- nicctl show dcqcn
- nicctl show environment
- nicctl show lif
- nicctl show pcie ats
- nicctl show port
- nicctl show qos
- nicctl show rdma statistics
- nicctl show version host-software
- nicctl show dcqcn --card {card_id} --json
- nicctl show card hardware-config --card {card_id}

## Collector Class NvmeCollector

### Description

Collect NVMe details from the system.

**Bases**: ['InBandDataCollector']

**Link to code**: [nvme_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nvme/nvme_collector.py)

### Class Variables

- **CMD_LINUX_LIST_JSON**: `nvme list -o json`
- **CMD_LINUX**: `{'smart_log': 'nvme smart-log {dev}', 'error_log': 'nvme error-log {dev} --log-entries=256', 'id_ctrl': 'nvme id-ctrl {dev}', 'id_ns': 'nvme id-ns {dev}{ns}', 'fw_log': 'nvme fw-log {dev}', 'self_test_log': 'nvme self-test-log {dev}', 'get_log': 'nvme get-log {dev} --log-id=6 --log-len=512', 'telemetry_log': 'nvme telemetry-log {dev} --output-file={dev}_{f_name}'}`
- **CMD_TEMPLATES**: `[
  nvme smart-log {dev},
  nvme error-log {dev} --log-entries=256,
  nvme id-ctrl {dev},
  nvme id-ns {dev}{ns},
  nvme fw-log {dev},
  nvme self-test-log {dev},
  nvme get-log {dev} --log-id=6 --log-len=512,
  nvme telemetry-log {dev} --output-file={dev}_{f_name}
]`
- **TELEMETRY_FILENAME**: `telemetry_log.bin`

### Provides Data

NvmeDataModel

### Commands

- nvme smart-log {dev}
- nvme error-log {dev} --log-entries=256
- nvme id-ctrl {dev}
- nvme id-ns {dev}{ns}
- nvme fw-log {dev}
- nvme self-test-log {dev}
- nvme get-log {dev} --log-id=6 --log-len=512
- nvme telemetry-log {dev} --output-file={dev}_{f_name}
- nvme list -o json

## Collector Class OsCollector

### Description

Collect OS details

**Bases**: ['InBandDataCollector']

**Link to code**: [os_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/os/os_collector.py)

### Class Variables

- **CMD_VERSION_WINDOWS**: `wmic os get Version /value`
- **CMD_VERSION**: `cat /etc/*release | grep VERSION_ID`
- **CMD_WINDOWS**: `wmic os get Caption /Value`
- **PRETTY_STR**: `PRETTY_NAME`
- **CMD**: `sh -c '( lsb_release -ds || (cat /etc/*release | grep PRETTY_NAME) || uname -om ) 2>/dev/null | head -n1'`

### Provides Data

OsDataModel

### Commands

- sh -c '( lsb_release -ds || (cat /etc/*release | grep PRETTY_NAME) || uname -om ) 2>/dev/null | head -n1'
- cat /etc/*release | grep VERSION_ID
- wmic os get Version /value
- wmic os get Caption /Value

## Collector Class PackageCollector

### Description

Collecting Package information from the system

**Bases**: ['InBandDataCollector']

**Link to code**: [package_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/package/package_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic product get name,version`
- **CMD_RELEASE**: `cat /etc/*release`
- **CMD_DPKG**: `dpkg-query -W`
- **CMD_DNF**: `dnf list --installed`
- **CMD_PACMAN**: `pacman -Q`

### Provides Data

PackageDataModel

### Commands

- dnf list --installed
- dpkg-query -W
- pacman -Q
- cat /etc/*release
- wmic product get name,version

## Collector Class PcieCollector

### Description

class for collection of PCIe data only supports Linux OS type.

    This class collects the PCIE config space using the lspci hex dump and then parses the hex dump to get the
    PCIe configuration space for the GPUs in the system. If the system interaction level is set to STANDARD or higher,
    then the entire pcie configuration space is collected for the GPUs in the system. If the system interaction level
    is set to SURFACE then, only the first 64 bytes of the pcie configuration space is collected for the GPUs in the system.

    This class will collect important PCIe data from the system running the commands
    - `lspci -vvv` : Verbose collection of PCIe data
    - `lspci -vvvt`: Verbose tree view of PCIe data
    - `lspci -PP`: Path view of PCIe data for the GPUs
    - If system interaction level is set to STANDARD or higher, the following commands will be run with sudo:
        - `lspci -xxxx`: Hex view of PCIe data for the GPUs
    - otherwise the following commands will be run without sudo:
        - `lspci -x`: Hex view of PCIe data for the GPUs
    - `lspci -d <vendor_id>:<dev_id>` : Count the number of GPUs in the system with this command
    - If system interaction level is set to STANDARD or higher, the following commands will be run with sudo:
        - The sudo lspci -xxxx command is used to collect the PCIe configuration space for the GPUs in the system
    - otherwise the following commands will be run without sudo:
        - The lspci -x command is used to collect the PCIe configuration space for the GPUs in the system

**Bases**: ['InBandDataCollector']

**Link to code**: [pcie_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/pcie/pcie_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_LSPCI_VERBOSE**: `lspci -vvv`
- **CMD_LSPCI_VERBOSE_TREE**: `lspci -vvvt`
- **CMD_LSPCI_PATH**: `lspci -PP`
- **CMD_LSPCI_HEX_SUDO**: `lspci -xxxx`
- **CMD_LSPCI_HEX**: `lspci -x`
- **CMD_LSPCI_AMD_DEVICES**: `lspci -d {vendor_id}: -nn`
- **CMD_LSPCI_PATH_DEVICE**: `lspci -PP -d {vendor_id}:{dev_id}`

### Provides Data

PcieDataModel

### Commands

- lspci -d {vendor_id}: -nn
- lspci -x
- lspci -xxxx
- lspci -PP
- lspci -PP -d {vendor_id}:{dev_id}
- lspci -vvv
- lspci -vvvt

## Collector Class ProcessCollector

### Description

Collect Process details

**Bases**: ['InBandDataCollector']

**Link to code**: [process_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/process/process_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_KFD**: `rocm-smi --showpids`
- **CMD_CPU_USAGE**: `top -b -n 1`
- **CMD_PROCESS**: `top -b -n 1 -o %CPU `

### Provides Data

ProcessDataModel

### Commands

- top -b -n 1
- rocm-smi --showpids
- top -b -n 1 -o %CPU

## Collector Class RdmaCollector

### Description

Collect RDMA status and statistics via rdma link and rdma statistic commands.

**Bases**: ['InBandDataCollector']

**Link to code**: [rdma_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rdma/rdma_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_LINK**: `rdma link -j`
- **CMD_STATISTIC**: `rdma statistic -j`
- **CMD_RDMA_DEV**: `rdma dev`
- **CMD_RDMA_LINK**: `rdma link`

### Provides Data

RdmaDataModel

### Commands

- rdma link -j
- rdma dev
- rdma link
- rdma statistic -j

## Collector Class RocmCollector

### Description

Collect ROCm version data

**Bases**: ['InBandDataCollector']

**Link to code**: [rocm_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocm_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_ROCM_SUB_VERSIONS_TMPL**: `grep . -r {rocm_path}/.info/*`
- **CMD_ROCMINFO_TMPL**: `{rocm_path}/bin/rocminfo`
- **CMD_ROCM_LATEST_TMPL**: `ls -v -d {rocm_path}-[3-7]* | tail -1`
- **CMD_ROCM_DIRS_TMPL**: `ls -v -d {rocm_path}*`
- **CMD_LD_CONF**: `grep -i -E 'rocm' /etc/ld.so.conf.d/*`
- **CMD_ROCM_LIBS**: `ldconfig -p | grep -i -E 'rocm'`
- **CMD_ENV_VARS**: `env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'`
- **CMD_CLINFO_TMPL**: `{rocm_path}/opencl/bin/*/clinfo`
- **CMD_KFD_PROC**: `ls /sys/class/kfd/kfd/proc/`

### Provides Data

RocmDataModel

### Commands

- {rocm_path}/opencl/bin/*/clinfo
- env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'
- ls /sys/class/kfd/kfd/proc/
- grep -i -E 'rocm' /etc/ld.so.conf.d/*
- {rocm_path}/bin/rocminfo
- ls -v -d {rocm_path}*
- ls -v -d {rocm_path}-[3-7]* | tail -1
- ldconfig -p | grep -i -E 'rocm'
- grep . -r {rocm_path}/.info/*

## Collector Class StorageCollector

### Description

Collect disk usage details

**Bases**: ['InBandDataCollector']

**Link to code**: [storage_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/storage/storage_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace`
- **CMD**: `sh -c 'df -lH -B1 | grep -v 'boot''`

### Provides Data

StorageDataModel

### Commands

- sh -c 'df -lH -B1 | grep -v 'boot''
- wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace

## Collector Class SysSettingsCollector

### Description

Collect sysfs settings from user-specified paths.

**Bases**: ['InBandDataCollector']

**Link to code**: [sys_settings_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sys_settings/sys_settings_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `cat /sys/{}`
- **CMD_LS**: `ls -1 /sys/{}`
- **CMD_LS_LONG**: `ls -l /sys/{}`

### Provides Data

SysSettingsDataModel

### Commands

- cat /sys/{}
- ls -1 /sys/{}
- ls -l /sys/{}

## Collector Class SysctlCollector

### Description

Collect sysctl kernel VM settings.

**Bases**: ['InBandDataCollector']

**Link to code**: [sysctl_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sysctl/sysctl_collector.py)

### Class Variables

- **CMD**: `sysctl -n`

### Provides Data

SysctlDataModel

### Commands

- sysctl -n

## Collector Class SyslogCollector

### Description

Read syslog log

**Bases**: ['InBandDataCollector']

**Link to code**: [syslog_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/syslog/syslog_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `ls -1 /var/log/syslog* 2>/dev/null | grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' || true`

### Provides Data

SyslogData

### Commands

- ls -1 /var/log/syslog* 2>/dev/null | grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' || true

## Collector Class UptimeCollector

### Description

Collect last boot time and uptime from uptime command

**Bases**: ['InBandDataCollector']

**Link to code**: [uptime_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/uptime/uptime_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `uptime`

### Provides Data

UptimeDataModel

### Commands

- uptime

# Data Models

## AmdSmiDataModel Model

### Description

Data model for amd-smi data.

    Optionals are used to allow for the data to be missing,
    This makes the data class more flexible for the analyzer
    which consumes only the required data. If any more data is
    required for the analyzer then they should not be set to
    default.

**Link to code**: [amdsmidata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/amdsmi/amdsmidata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **version**: `Optional[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiVersion]`
- **gpu_list**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiListItem]]`
- **partition**: `Optional[nodescraper.plugins.inband.amdsmi.amdsmidata.Partition]`
- **process**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.Processes]]`
- **topology**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.Topo]]`
- **firmware**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.Fw]]`
- **bad_pages**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.BadPages]]`
- **static**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiStatic]]`
- **metric**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiMetric]]`
- **xgmi_metric**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.XgmiMetrics]]`
- **xgmi_link**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.XgmiLinks]]`
- **cper_data**: `Optional[list[nodescraper.models.datamodel.FileModel]]`
- **cper_afids**: `dict[str, int]`

## BiosDataModel Model

**Link to code**: [biosdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/bios/biosdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **bios_version**: `str`

## CmdlineDataModel Model

**Link to code**: [cmdlinedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/cmdline/cmdlinedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **cmdline**: `str`

## DeviceEnumerationDataModel Model

**Link to code**: [deviceenumdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/device_enumeration/deviceenumdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **cpu_count**: `Optional[int]`
- **gpu_count**: `Optional[int]`
- **vf_count**: `Optional[int]`
- **lscpu_output**: `Optional[str]`
- **lshw_output**: `Optional[str]`

## DimmDataModel Model

**Link to code**: [dimmdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dimm/dimmdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **dimms**: `str`

## DkmsDataModel Model

**Link to code**: [dkmsdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dkms/dkmsdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **status**: `Optional[str]`
- **version**: `Optional[str]`

## DmesgData Model

### Description

Data model for in band dmesg log

**Link to code**: [dmesgdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dmesg/dmesgdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **dmesg_content**: `str`
- **skip_log_file**: `bool`

## FabricsDataModel Model

### Description

Complete InfiniBand/RDMA fabrics configuration data

**Link to code**: [fabricsdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/fabrics/fabricsdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **ibstat_devices**: `List[nodescraper.plugins.inband.fabrics.fabricsdata.IbstatDevice]`
- **ibv_devices**: `List[nodescraper.plugins.inband.fabrics.fabricsdata.IbvDeviceInfo]`
- **ibdev_netdev_mappings**: `List[nodescraper.plugins.inband.fabrics.fabricsdata.IbdevNetdevMapping]`
- **ofed_info**: `Optional[nodescraper.plugins.inband.fabrics.fabricsdata.OfedInfo]`
- **mst_status**: `Optional[nodescraper.plugins.inband.fabrics.fabricsdata.MstStatus]`
- **slingshot_data**: `Optional[nodescraper.plugins.inband.fabrics.fabricsdata.SlingshotData]`

## JournalData Model

### Description

Data model for journal logs

**Link to code**: [journaldata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/journaldata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **journal_log**: `str`
- **journal_content_json**: `list[nodescraper.plugins.inband.journal.journaldata.JournalJsonEntry]`

## KernelDataModel Model

**Link to code**: [kerneldata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/kerneldata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_info**: `str`
- **kernel_version**: `str`
- **numa_balancing**: `Optional[int]`

## KernelModuleDataModel Model

**Link to code**: [kernel_module_data.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/kernel_module_data.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_modules**: `dict`
- **amdgpu_modinfo**: `Optional[nodescraper.plugins.inband.kernel_module.kernel_module_data.ModuleInfo]`

## MemoryDataModel Model

### Description

Memory data model

**Link to code**: [memorydata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/memorydata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **mem_free**: `str`
- **mem_total**: `str`
- **lsmem_data**: `Optional[nodescraper.plugins.inband.memory.memorydata.LsmemData]`
- **numa_topology**: `Optional[nodescraper.plugins.inband.memory.memorydata.NumaTopology]`

## NetworkDataModel Model

### Description

Complete network configuration data

**Link to code**: [networkdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/network/networkdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **interfaces**: `List[nodescraper.plugins.inband.network.networkdata.NetworkInterface]`
- **routes**: `List[nodescraper.plugins.inband.network.networkdata.Route]`
- **rules**: `List[nodescraper.plugins.inband.network.networkdata.RoutingRule]`
- **neighbors**: `List[nodescraper.plugins.inband.network.networkdata.Neighbor]`
- **ethtool_info**: `Dict[str, nodescraper.plugins.inband.network.networkdata.EthtoolInfo]`
- **accessible**: `Optional[bool]`

## NicDataModel Model

### Description

Collected output of niccli (Broadcom) and nicctl (Pensando) commands.

**Link to code**: [nic_data.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nic/nic_data.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **results**: `Dict[str, nodescraper.plugins.inband.nic.nic_data.NicCommandResult]`
- **card_show**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlCardShow]`
- **cards**: `List[nodescraper.plugins.inband.nic.nic_data.NicCtlCard]`
- **port**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlPort]`
- **lif**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlLif]`
- **qos**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlQos]`
- **rdma**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlRdma]`
- **dcqcn**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlDcqcn]`
- **environment**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlEnvironment]`
- **version**: `Optional[nodescraper.plugins.inband.nic.nic_data.NicCtlVersion]`
- **broadcom_nic_devices**: `List[nodescraper.plugins.inband.nic.nic_data.NicCliDevice]`
- **broadcom_nic_qos**: `Dict[int, nodescraper.plugins.inband.nic.nic_data.NicCliQos]`
- **broadcom_nic_support_rdma**: `Dict[int, str]`
- **broadcom_nic_performance_profile**: `Dict[int, str]`
- **broadcom_nic_pcie_relaxed_ordering**: `Dict[int, str]`
- **pensando_nic_cards**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicCard]`
- **pensando_nic_dcqcn**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicDcqcn]`
- **pensando_nic_environment**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicEnvironment]`
- **pensando_nic_lif**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicLif]`
- **pensando_nic_pcie_ats**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicPcieAts]`
- **pensando_nic_ports**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicPort]`
- **pensando_nic_qos**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicQos]`
- **pensando_nic_rdma_statistics**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicRdmaStatistics]`
- **pensando_nic_version_host_software**: `Optional[nodescraper.plugins.inband.nic.nic_data.PensandoNicVersionHostSoftware]`
- **pensando_nic_version_firmware**: `List[nodescraper.plugins.inband.nic.nic_data.PensandoNicVersionFirmware]`
- **nicctl_card_logs**: `Optional[Dict[str, str]]`

## NvmeDataModel Model

### Description

NVMe collection output: parsed 'nvme list' entries and per-device command outputs.

**Link to code**: [nvmedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nvme/nvmedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **nvme_list**: `Optional[list[nodescraper.plugins.inband.nvme.nvmedata.NvmeListEntry]]`
- **devices**: `dict[str, nodescraper.plugins.inband.nvme.nvmedata.DeviceNvmeData]`

## OsDataModel Model

**Link to code**: [osdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/os/osdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **os_name**: `str`
- **os_version**: `str`

## PackageDataModel Model

### Description

Pacakge data contains the package data for the system

**Link to code**: [packagedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/package/packagedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **version_info**: `dict[str, str]`
- **rocm_regex**: `str`
- **enable_rocm_regex**: `bool`

## PcieDataModel Model

### Description

class for collection of PCIe data.

    Optionals are used to allow for the data to be missing,
    This makes the data class more flexible for the analyzer
    which consumes only the required data. If any more data is
    required for the analyzer then they should not be set to
    default.

    - pcie_cfg_space: A dictionary of PCIe cfg space for the GPUs obtained with setpci command
    - lspci_verbose: Verbose collection of PCIe data
    - lspci_verbose_tree: Tree view of PCIe data
    - lspci_path: Path view of PCIe data for the GPUs
    - lspci_hex: Hex view of PCIe data for the GPUs

**Link to code**: [pcie_data.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/pcie/pcie_data.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **pcie_cfg_space**: `Dict[Annotated[str, AfterValidator(func=validate_bdf)], nodescraper.plugins.inband.pcie.pcie_data.PcieCfgSpace]`
- **vf_pcie_cfg_space**: `Optional[Dict[Annotated[str, AfterValidator(func=validate_bdf)], nodescraper.plugins.inband.pcie.pcie_data.PcieCfgSpace]]`

## ProcessDataModel Model

**Link to code**: [processdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/process/processdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **kfd_process**: `Optional[int]`
- **cpu_usage**: `Optional[float]`
- **processes**: `Optional[list[tuple[str, str]]]`

## RdmaDataModel Model

### Description

Data model for RDMA (Remote Direct Memory Access) statistics and link information.

**Link to code**: [rdmadata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rdma/rdmadata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **link_list**: `list[nodescraper.plugins.inband.rdma.rdmadata.RdmaLink]`
- **statistic_list**: `list[nodescraper.plugins.inband.rdma.rdmadata.RdmaStatistics]`
- **dev_list**: `list[nodescraper.plugins.inband.rdma.rdmadata.RdmaDevice]`
- **link_list_text**: `list[nodescraper.plugins.inband.rdma.rdmadata.RdmaLinkText]`

## RocmDataModel Model

**Link to code**: [rocmdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocmdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **rocm_version**: `str`
- **rocm_sub_versions**: `dict[str, str]`
- **rocminfo**: `List[str]`
- **rocm_latest_versioned_path**: `str`
- **rocm_all_paths**: `List[str]`
- **ld_conf_rocm**: `List[str]`
- **rocm_libs**: `List[str]`
- **env_vars**: `List[str]`
- **clinfo**: `List[str]`
- **kfd_proc**: `List[str]`

## StorageDataModel Model

**Link to code**: [storagedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/storage/storagedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **storage_data**: `dict[str, nodescraper.plugins.inband.storage.storagedata.DeviceStorageData]`

## SysSettingsDataModel Model

### Description

Data model for sysfs settings: path -> parsed value.

    Values are parsed from user-specified sysfs paths (bracketed value extracted
    when present, e.g. '[always] madvise never' -> 'always').

**Link to code**: [sys_settings_data.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sys_settings/sys_settings_data.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **readings**: `dict[str, str]`

## SysctlDataModel Model

**Link to code**: [sysctldata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sysctl/sysctldata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **vm_swappiness**: `Optional[int]`
- **vm_numa_balancing**: `Optional[int]`
- **vm_oom_kill_allocating_task**: `Optional[int]`
- **vm_compaction_proactiveness**: `Optional[int]`
- **vm_compact_unevictable_allowed**: `Optional[int]`
- **vm_extfrag_threshold**: `Optional[int]`
- **vm_zone_reclaim_mode**: `Optional[int]`
- **vm_dirty_background_ratio**: `Optional[int]`
- **vm_dirty_ratio**: `Optional[int]`
- **vm_dirty_writeback_centisecs**: `Optional[int]`
- **kernel_numa_balancing**: `Optional[int]`

## SyslogData Model

### Description

Data model for in band syslog logs

**Link to code**: [syslogdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/syslog/syslogdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **syslog_logs**: `list[nodescraper.connection.inband.inband.TextFileArtifact]`

## UptimeDataModel Model

**Link to code**: [uptimedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/uptime/uptimedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **current_time**: `str`
- **uptime**: `str`

# Data Analyzers

## Data Analyzer Class AmdSmiAnalyzer

### Description

Check AMD SMI Application data for PCIe, ECC errors, and CPER data.

**Bases**: ['CperAnalysisTaskMixin', 'DataAnalyzer']

**Link to code**: [amdsmi_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/amdsmi/amdsmi_analyzer.py)

## Data Analyzer Class BiosAnalyzer

### Description

Check bios matches expected bios details

**Bases**: ['DataAnalyzer']

**Link to code**: [bios_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/bios/bios_analyzer.py)

## Data Analyzer Class CmdlineAnalyzer

### Description

Check cmdline matches expected kernel cmdline

**Bases**: ['DataAnalyzer']

**Link to code**: [cmdline_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/cmdline/cmdline_analyzer.py)

## Data Analyzer Class DeviceEnumerationAnalyzer

### Description

Check Device Enumeration matches expected cpu and gpu count
    supported by all OSs, SKUs, and platforms.

**Bases**: ['DataAnalyzer']

**Link to code**: [device_enumeration_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/device_enumeration/device_enumeration_analyzer.py)

## Data Analyzer Class DkmsAnalyzer

### Description

Check dkms matches expected status and version

**Bases**: ['DataAnalyzer']

**Link to code**: [dkms_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dkms/dkms_analyzer.py)

## Data Analyzer Class DmesgAnalyzer

### Description

Check dmesg for errors

**Bases**: ['RegexAnalyzer']

**Link to code**: [dmesg_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dmesg/dmesg_analyzer.py)

### Class Variables

- **ERROR_REGEX**: `[
  regex=re.compile('(?:oom_kill_process.*)|(?:Out of memory.*)') message='Out of memory error' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('IO_PAGE_FAULT') message='I/O Page Fault' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\bkernel panic\\b.*', re.IGNORECASE) message='Kernel Panic' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('sq_intr') message='SQ Interrupt' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('sram_ecc.*') message='SRAM ECC' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\[amdgpu\\]\\] \\*ERROR\\* hw_init of IP block.*') message='Failed to load driver. IP hardware init error.' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\[amdgpu\\]\\] \\*ERROR\\* sw_init of IP block.*') message='Failed to load driver. IP software init error.' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('sched: RT throttling activated.*') message='Real Time throttling activated' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('rcu_preempt detected stalls.*') message='RCU preempt detected stalls' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('rcu_preempt self-detected stall.*') message='RCU preempt self-detected stall' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('qcm fence wait loop timeout.*') message='QCM fence timeout' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:[\\w-]+(?:\\[[0-9.]+\\])?\\s+)?general protection fault[^\\n]*') message='General protection fault' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:segfault.*in .*\\[)|(?:[Ss]egmentation [Ff]ault.*)|(?:[Ss]egfault.*)') message='Segmentation fault' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('amdgpu: Failed to disallow cf state.*') message='Failed to disallow cf state' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\*ERROR\\* Failed to terminate tmr.*') message='Failed to terminate tmr' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\*ERROR\\* suspend of IP block <\\w+> failed.*') message='Suspend of IP block failed' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(amdgpu \\w{4}:\\w{2}:\\w{2}\\.\\w:\\s+amdgpu:\\s+\\[\\S+\\]\\s*(?:retry|no-retry)? page fault[^\\n]*)(?:\\n[^\\n]*(amdgpu \\w{4}:\\w{2}:\\w{2}\\.\\w:\\s+amdgpu:[^\\n]*))?(?:\\n[^\\n]*(amdgpu \\w{4}:, re.MULTILINE) message='amdgpu Page Fault' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('page fault for address.*') message='Page Fault' event_category=<EventCategory.OS: 'OS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:amdgpu)(.*Fatal error during GPU init)|(Fatal error during GPU init)') message='Fatal error during GPU init' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(pcieport [\\w:.]+: AER: aer_status:[^\\n]*(?:\\n[^\\n]*){0,32}?pcieport [\\w:.]+: AER: aer_layer=[^\\n]*)', re.MULTILINE) message='PCIe AER Error Status' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(.*aer_cor_status: 0x[0-9a-fA-F]+, aer_cor_mask: 0x[0-9a-fA-F]+.*)') message='PCIe AER Correctable Error Status' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(.*aer_uncor_status: 0x[0-9a-fA-F]+, aer_uncor_mask: 0x[0-9a-fA-F]+.*)') message='PCIe AER Uncorrectable Error Status' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(.*aer_uncor_severity: 0x[0-9a-fA-F]+.*)(\\n.*TLP Header: (?:0x)?[0-9a-fA-F]+(?: (?:0x)?[0-9a-fA-F]+){3}.*)', re.MULTILINE) message='PCIe AER Uncorrectable Error Severity with TLP Header' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('Failed to read journal file.*') message='Failed to read journal file' event_category=<EventCategory.OS: 'OS'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('journal corrupted or uncleanly shut down.*') message='Journal file corrupted or uncleanly shut down' event_category=<EventCategory.OS: 'OS'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('ACPI BIOS Error') message='ACPI BIOS Error' event_category=<EventCategory.BIOS: 'BIOS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('ACPI Error') message='ACPI Error' event_category=<EventCategory.BIOS: 'BIOS'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('EXT4-fs error \\(device .*\\):') message='Filesystem corrupted!' event_category=<EventCategory.OS: 'OS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(Buffer I\\/O error on dev)(?:ice)? (\\w+)') message='Error in buffered IO, check filesystem integrity' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(Slot\\(\\d+\\)):\\s+(Card not present)') message='PCIe card no longer present' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(Slot\\(\\d+\\)):\\s+(Link Down)') message='PCIe Link Down' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(current common clock configuration is inconsistent, reconfiguring)') message='Mismatched clock configuration between PCIe device and host' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* correctable hardware errors detected in total in \\w+ block.*)') message='RAS Correctable Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* uncorrectable hardware errors detected in \\w+ block.*)') message='RAS Uncorrectable Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* deferred hardware errors detected in \\w+ block.*)') message='RAS Deferred Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('((?:\\[Hardware Error\\]:\\s+)?event severity: corrected.*)\\n.*(\\[Hardware Error\\]:\\s+Error \\d+, type: corrected.*)\\n.*(\\[Hardware Error\\]:\\s+section_type: PCIe error.*)') message='RAS Corrected PCIe Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*GPU reset begin.*)') message='GPU Reset' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*GPU reset(?:\\(\\d+\\))? failed.*)') message='GPU reset failed' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(Accelerator Check Architecture[^\\n]*)(?:\\n[^\\n]*){0,10}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*entry\\[\\d+\\]\\.STATUS=0x[0-9a-fA-F]+)(?:\\n[^\\n]*){0,5}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*entry\\[\\d+\\], re.MULTILINE) message='ACA Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(Accelerator Check Architecture[^\\n]*)(?:\\n[^\\n]*){0,10}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*CONTROL=0x[0-9a-fA-F]+)(?:\\n[^\\n]*){0,5}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*STATUS=0x[0-9a-fA-F]+)(?:\\n[^\\, re.MULTILINE) message='ACA Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('\\[Hardware Error\\]:.+MC\\d+_STATUS.*(?:\\n.*){0,5}') message='MCE Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)? (.*Mode2 reset failed.*)') message='Mode 2 Reset Failed' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*\\[Hardware Error\\]: Corrected error.*)') message='RAS Corrected Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('x86/cpu: SGX disabled by BIOS') message='SGX Error' event_category=<EventCategory.BIOS: 'BIOS'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('Failed to load MMP firmware qat_4xxx_mmp.bin') message='MMP Error' event_category=<EventCategory.BIOS: 'BIOS'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('amdgpu \\w{4}:\\w{2}:\\w{2}.\\w: amdgpu: WARN: GPU is throttled.*') message='GPU Throttled' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('amdgpu[ 0-9a-fA-F:.]+:(?:\\s*amdgpu:)?\\s+(?:{\\d+})?poison is consumed by client \\d+, kick off gpu reset flow') message='RAS Poison Consumed' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('amdgpu[ 0-9a-fA-F:.]+:(?:\\s*amdgpu:)?\\s+(?:{\\d+})?Poison is created') message='RAS Poison created' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(amdgpu: Saved bad pages (\\d+) reaches threshold value 128)') message='Bad page threshold exceeded' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('Hardware error from APEI Generic Hardware Error Source:.*(?:\\n.*){0,14}') message='RAS Hardware Error' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('Error Address.*(?:\\s.*)') message='Error Address' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('EDR: EDR event received') message='RAS EDR Event' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('DPC: .*') message='DPC Event' event_category=<EventCategory.RAS: 'RAS'> event_priority=<EventPriority.ERROR: 3>,
  regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:.*ko2iblnd:\\s*No matching interfaces', re.IGNORECASE) message='LNet: ko2iblnd has no matching interfaces' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:\\s*.*Error\\s*-?\\d+\\s+starting up LNI\\s+\\w+', re.IGNORECASE) message='LNet: Error starting up LNI' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('LustreError:.*ptlrpc_init_portals\\(\\).*network initiali[sz]ation failed', re.IGNORECASE) message='Lustre: network initialisation failed' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>
]`

### Regex Patterns

*57 items defined*

- **Built-in Regexes:**
- - Out of memory error: `(?:oom_kill_process.*)|(?:Out of memory.*)`
- - I/O Page Fault: `IO_PAGE_FAULT`
- - Kernel Panic: `\bkernel panic\b.*`
- - SQ Interrupt: `sq_intr`
- - SRAM ECC: `sram_ecc.*`
- - Failed to load driver. IP hardware init error.: `\[amdgpu\]\] \*ERROR\* hw_init of IP block.*`
- - Failed to load driver. IP software init error.: `\[amdgpu\]\] \*ERROR\* sw_init of IP block.*`
- - Real Time throttling activated: `sched: RT throttling activated.*`
- - RCU preempt detected stalls: `rcu_preempt detected stalls.*`
- - RCU preempt self-detected stall: `rcu_preempt self-detected stall.*`
- - QCM fence timeout: `qcm fence wait loop timeout.*`
- - General protection fault: `(?:[\w-]+(?:\[[0-9.]+\])?\s+)?general protectio...`
- - Segmentation fault: `(?:segfault.*in .*\[)|(?:[Ss]egmentation [Ff]au...`
- - Failed to disallow cf state: `amdgpu: Failed to disallow cf state.*`
- - Failed to terminate tmr: `\*ERROR\* Failed to terminate tmr.*`
- - Suspend of IP block failed: `\*ERROR\* suspend of IP block <\w+> failed.*`
- - amdgpu Page Fault: `(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:\s+\[\S...`
- - Page Fault: `page fault for address.*`
- - Fatal error during GPU init: `(?:amdgpu)(.*Fatal error during GPU init)|(Fata...`
- - PCIe AER Error Status: `(pcieport [\w:.]+: AER: aer_status:[^\n]*(?:\n[...`
- - PCIe AER Correctable Error Status: `(.*aer_cor_status: 0x[0-9a-fA-F]+, aer_cor_mask...`
- - PCIe AER Uncorrectable Error Status: `(.*aer_uncor_status: 0x[0-9a-fA-F]+, aer_uncor_...`
- - PCIe AER Uncorrectable Error Severity with TLP Header: `(.*aer_uncor_severity: 0x[0-9a-fA-F]+.*)(\n.*TL...`
- - Failed to read journal file: `Failed to read journal file.*`
- - Journal file corrupted or uncleanly shut down: `journal corrupted or uncleanly shut down.*`
- - ACPI BIOS Error: `ACPI BIOS Error`
- - ACPI Error: `ACPI Error`
- - Filesystem corrupted!: `EXT4-fs error \(device .*\):`
- - Error in buffered IO, check filesystem integrity: `(Buffer I\/O error on dev)(?:ice)? (\w+)`
- - PCIe card no longer present: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`
- - PCIe Link Down: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`
- - Mismatched clock configuration between PCIe device and host: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(curren...`
- - RAS Correctable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - RAS Uncorrectable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - RAS Deferred Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - RAS Corrected PCIe Error: `((?:\[Hardware Error\]:\s+)?event severity: cor...`
- - GPU Reset: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - GPU reset failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`
- - ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`
- - MCE Error: `\[Hardware Error\]:.+MC\d+_STATUS.*(?:\n.*){0,5}`
- - Mode 2 Reset Failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)? (...`
- - RAS Corrected Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`
- - SGX Error: `x86/cpu: SGX disabled by BIOS`
- - MMP Error: `Failed to load MMP firmware qat_4xxx_mmp.bin`
- - GPU Throttled: `amdgpu \w{4}:\w{2}:\w{2}.\w: amdgpu: WARN: GPU ...`
- - RAS Poison Consumed: `amdgpu[ 0-9a-fA-F:.]+:(?:\s*amdgpu:)?\s+(?:{\d+...`
- - RAS Poison created: `amdgpu[ 0-9a-fA-F:.]+:(?:\s*amdgpu:)?\s+(?:{\d+...`
- - Bad page threshold exceeded: `(amdgpu: Saved bad pages (\d+) reaches threshol...`
- - RAS Hardware Error: `Hardware error from APEI Generic Hardware Error...`
- - Error Address: `Error Address.*(?:\s.*)`
- - RAS EDR Event: `EDR: EDR event received`
- - DPC Event: `DPC: .*`
- - LNet: ko2iblnd has no matching interfaces: `(?:\[[^\]]+\]\s*)?LNetError:.*ko2iblnd:\s*No ma...`
- - LNet: Error starting up LNI: `(?:\[[^\]]+\]\s*)?LNetError:\s*.*Error\s*-?\d+\...`
- - Lustre: network initialisation failed: `LustreError:.*ptlrpc_init_portals\(\).*network ...`

## Data Analyzer Class JournalAnalyzer

### Description

Check journalctl for errors

**Bases**: ['DataAnalyzer']

**Link to code**: [journal_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/journal_analyzer.py)

## Data Analyzer Class KernelAnalyzer

### Description

Check kernel matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: [kernel_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/kernel_analyzer.py)

## Data Analyzer Class KernelModuleAnalyzer

### Description

Check kernel matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: [kernel_module_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/kernel_module_analyzer.py)

## Data Analyzer Class MemoryAnalyzer

### Description

Check memory usage is within the maximum allowed used memory

**Bases**: ['DataAnalyzer']

**Link to code**: [memory_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/memory_analyzer.py)

## Data Analyzer Class NicAnalyzer

### Description

Analyze niccli/nicctl data; checks Broadcom support_rdma, performance_profile (RoCE), pcie_relaxed_ordering (enabled), and getqos (expected QoS across adapters).

**Bases**: ['DataAnalyzer']

**Link to code**: [nic_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nic/nic_analyzer.py)

## Data Analyzer Class OsAnalyzer

### Description

Check os matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: [os_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/os/os_analyzer.py)

## Data Analyzer Class PackageAnalyzer

### Description

Check the package version data against the expected package version data

**Bases**: ['DataAnalyzer']

**Link to code**: [package_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/package/package_analyzer.py)

## Data Analyzer Class PcieAnalyzer

### Description

Check PCIe Data for errors

    This calls checks the following:
    - PCIe link status for each BDF
        - This checks if the link speed and width are as expected
    - AER uncorrectable errors
        - Checks PCIe AER uncorrectable error registers UNCORR_ERR_STAT_REG and reports any errors
    - AER correctable errors
        - Checks the AERs correctable error registers CORR_ERR_STAT_REG and reports any errors
    - PCIe device status errors
        - Checks PCIe device status errors reported in fields `CORR_ERR_DET` `NON_FATAL_ERR_DET` `FATAL_ERR_DET` `UR_DET`
    - PCIe status errors
        - Checks PCIe status errors reported in fields `MSTR_DATA_PAR_ERR` `SIGNALED_TARGET_ABORT` `RCVD_TARGET_ABORT`
            `RCVD_MSTR_ABORT` `SIGNALED_SYS_ERR` `DET_PARITY_ERR`

**Bases**: ['DataAnalyzer']

**Link to code**: [pcie_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/pcie/pcie_analyzer.py)

### Class Variables

- **GPU_BRIDGE_USP_ID**: `0x1501`
- **GPU_BRIDGE_DSP_ID**: `0x1500`

## Data Analyzer Class ProcessAnalyzer

### Description

Check cpu and kfd processes are within allowed maximum cpu and gpu usage

**Bases**: ['DataAnalyzer']

**Link to code**: [process_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/process/process_analyzer.py)

## Data Analyzer Class RdmaAnalyzer

### Description

Check RDMA statistics for errors (RoCE and other RDMA error counters).

**Bases**: ['DataAnalyzer']

**Link to code**: [rdma_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rdma/rdma_analyzer.py)

### Class Variables

- **ERROR_FIELDS**: `[
  recoverable_errors,
  tx_roce_errors,
  tx_roce_discards,
  rx_roce_errors,
  rx_roce_discards,
  local_ack_timeout_err,
  packet_seq_err,
  max_retry_exceeded,
  rnr_nak_retry_err,
  implied_nak_seq_err,
  unrecoverable_err,
  bad_resp_err,
  local_qp_op_err,
  local_protection_err,
  mem_mgmt_op_err,
  req_remote_invalid_request,
  req_remote_access_errors,
  remote_op_err,
  duplicate_request,
  res_exceed_max,
  resp_local_length_error,
  res_exceeds_wqe,
  res_opcode_err,
  res_rx_invalid_rkey,
  res_rx_domain_err,
  res_rx_no_perm,
  res_rx_range_err,
  res_tx_invalid_rkey,
  res_tx_domain_err,
  res_tx_no_perm,
  res_tx_range_err,
  res_irrq_oflow,
  res_unsup_opcode,
  res_unaligned_atomic,
  res_rem_inv_err,
  res_mem_err,
  res_srq_err,
  res_cmp_err,
  res_invalid_dup_rkey,
  res_wqe_format_err,
  res_cq_load_err,
  res_srq_load_err,
  res_tx_pci_err,
  res_rx_pci_err,
  out_of_buffer,
  out_of_sequence,
  req_cqe_error,
  req_cqe_flush_error,
  resp_cqe_error,
  resp_cqe_flush_error,
  resp_remote_access_errors,
  req_rx_pkt_seq_err,
  req_rx_rnr_retry_err,
  req_rx_rmt_acc_err,
  req_rx_rmt_req_err,
  req_rx_oper_err,
  req_rx_impl_nak_seq_err,
  req_rx_cqe_err,
  req_rx_cqe_flush,
  req_rx_dup_response,
  req_rx_inval_pkts,
  req_tx_loc_acc_err,
  req_tx_loc_oper_err,
  req_tx_mem_mgmt_err,
  req_tx_retry_excd_err,
  req_tx_loc_sgl_inv_err,
  resp_rx_dup_request,
  resp_rx_outof_buf,
  resp_rx_outouf_seq,
  resp_rx_cqe_err,
  resp_rx_cqe_flush,
  resp_rx_loc_len_err,
  resp_rx_inval_request,
  resp_rx_loc_oper_err,
  resp_rx_outof_atomic,
  resp_tx_pkt_seq_err,
  resp_tx_rmt_inval_req_err,
  resp_tx_rmt_acc_err,
  resp_tx_rmt_oper_err,
  resp_tx_rnr_retry_err,
  resp_tx_loc_sgl_inv_err,
  resp_rx_s0_table_err,
  resp_rx_ccl_cts_outouf_seq,
  tx_rdma_ack_timeout,
  tx_rdma_ccl_cts_ack_timeout,
  rx_rdma_mtu_discard_pkts
]`
- **CRITICAL_ERROR_FIELDS**: `['unrecoverable_err', 'res_tx_pci_err', 'res_rx_pci_err', 'res_mem_err']`

## Data Analyzer Class RocmAnalyzer

### Description

Check ROCm matches expected versions.

    The expected ROCm version (exp_rocm) can be a string or a list of allowed strings.
    Sub-versions (exp_rocm_sub_versions) are a dict: each value can be a string or
    a list of allowed strings for that key.

**Bases**: ['DataAnalyzer']

**Link to code**: [rocm_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocm_analyzer.py)

## Data Analyzer Class StorageAnalyzer

### Description

Check storage usage

**Bases**: ['DataAnalyzer']

**Link to code**: [storage_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/storage/storage_analyzer.py)

## Data Analyzer Class SysSettingsAnalyzer

### Description

Check sysfs settings against expected values from the checks list.

**Bases**: ['DataAnalyzer']

**Link to code**: [sys_settings_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sys_settings/sys_settings_analyzer.py)

## Data Analyzer Class SysctlAnalyzer

### Description

Check sysctl matches expected sysctl details

**Bases**: ['DataAnalyzer']

**Link to code**: [sysctl_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sysctl/sysctl_analyzer.py)

# Analyzer Args

## Analyzer Args Class AmdSmiAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/amdsmi/analyzer_args.py)

### Annotations / fields

- **check_static_data**: `bool` — If True, run static data checks (e.g. driver version, partition mode).
- **expected_gpu_processes**: `Optional[int]` — Expected number of GPU processes.
- **expected_max_power**: `Optional[int]` — Expected maximum power value (e.g. watts).
- **expected_driver_version**: `Optional[str]` — Expected AMD driver version string.
- **expected_memory_partition_mode**: `Optional[str]` — Expected memory partition mode (e.g. sp3, dp).
- **expected_compute_partition_mode**: `Optional[str]` — Expected compute partition mode.
- **expected_pldm_version**: `Optional[str]` — Expected PLDM version string.
- **l0_to_recovery_count_error_threshold**: `Optional[int]` — L0-to-recovery count above which an error is raised.
- **l0_to_recovery_count_warning_threshold**: `Optional[int]` — L0-to-recovery count above which a warning is raised.
- **vendorid_ep**: `Optional[str]` — Expected endpoint vendor ID (e.g. for PCIe).
- **vendorid_ep_vf**: `Optional[str]` — Expected endpoint VF vendor ID.
- **devid_ep**: `Optional[str]` — Expected endpoint device ID.
- **devid_ep_vf**: `Optional[str]` — Expected endpoint VF device ID.
- **sku_name**: `Optional[str]` — Expected SKU name string for GPU.
- **expected_xgmi_speed**: `Optional[list[float]]` — Expected xGMI speed value(s) (e.g. link rate).
- **analysis_range_start**: `Optional[datetime.datetime]` — Start of time range for time-windowed analysis.
- **analysis_range_end**: `Optional[datetime.datetime]` — End of time range for time-windowed analysis.

## Analyzer Args Class BiosAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/bios/analyzer_args.py)

### Annotations / fields

- **exp_bios_version**: `list[str]` — Expected BIOS version(s) to match against collected value (str or list).
- **regex_match**: `bool` — If True, match exp_bios_version as regex; otherwise exact match.

## Analyzer Args Class CmdlineAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/cmdline/analyzer_args.py)

### Annotations / fields

- **required_cmdline**: `Union[str, List]` — Command-line parameters that must be present (e.g. 'pci=bfsort').
- **banned_cmdline**: `Union[str, List]` — Command-line parameters that must not be present.
- **os_overrides**: `Dict[str, nodescraper.plugins.inband.cmdline.cmdlineconfig.OverrideConfig]` — Per-OS overrides for required_cmdline and banned_cmdline (keyed by OS identifier).
- **platform_overrides**: `Dict[str, nodescraper.plugins.inband.cmdline.cmdlineconfig.OverrideConfig]` — Per-platform overrides for required_cmdline and banned_cmdline (keyed by platform).

## Analyzer Args Class DeviceEnumerationAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/device_enumeration/analyzer_args.py)

### Annotations / fields

- **cpu_count**: `Optional[list[int]]` — Expected CPU count(s); pass as int or list of ints. Analysis passes if actual is in list.
- **gpu_count**: `Optional[list[int]]` — Expected GPU count(s); pass as int or list of ints. Analysis passes if actual is in list.
- **vf_count**: `Optional[list[int]]` — Expected virtual function count(s); pass as int or list of ints. Analysis passes if actual is in list.

## Analyzer Args Class DkmsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dkms/analyzer_args.py)

### Annotations / fields

- **dkms_status**: `Union[str, list]` — Expected dkms status string(s) to match (e.g. 'amd/1.0.0'). At least one of dkms_status or dkms_version required.
- **dkms_version**: `Union[str, list]` — Expected dkms version string(s) to match. At least one of dkms_status or dkms_version required.
- **regex_match**: `bool` — If True, match dkms_status and dkms_version as regex; otherwise exact match.

## Analyzer Args Class JournalAnalyzerArgs

### Description

Arguments for journal analyzer

**Bases**: ['TimeRangeAnalysisArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/analyzer_args.py)

### Annotations / fields

- **analysis_range_start**: `Optional[datetime.datetime]` — Start of time range for analysis (ISO format). Only events on or after this time are analyzed.
- **analysis_range_end**: `Optional[datetime.datetime]` — End of time range for analysis (ISO format). Only events before this time are analyzed.
- **check_priority**: `Optional[int]` — Check against journal log priority (0=emergency..7=debug). If an entry has priority <= check_priority, an ERROR event is raised.
- **group**: `bool` — If True, group entries that have the same priority and message.

## Analyzer Args Class KernelAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/analyzer_args.py)

### Annotations / fields

- **exp_kernel**: `Union[str, list]` — Expected kernel version string(s) to match (e.g. from uname -a).
- **exp_numa**: `Optional[int]` — Expected value for kernel.numa_balancing (e.g. 0 or 1).
- **regex_match**: `bool` — If True, match exp_kernel as regex; otherwise exact match.

## Analyzer Args Class KernelModuleAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/analyzer_args.py)

### Annotations / fields

- **kernel_modules**: `dict[str, dict]` — Expected kernel module name -> {version, etc.}. Analyzer checks collected modules match.
- **regex_filter**: `list[str]` — List of regex patterns to filter which collected modules are checked (default: amd).

## Analyzer Args Class MemoryAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/analyzer_args.py)

### Annotations / fields

- **ratio**: `float` — Required free-memory ratio (0-1). Analysis fails if free/total < ratio.
- **memory_threshold**: `str` — Minimum free memory required (e.g. '30Gi', '1T'). Used when ratio is not sufficient.

## Analyzer Args Class NicAnalyzerArgs

### Description

Analyzer args for niccli/nicctl data, with expected_values keyed by canonical command key.

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nic/analyzer_args.py)

### Annotations / fields

- **expected_values**: `Optional[Dict[str, Dict[str, Any]]]` — Per-command expected checks keyed by canonical key (see command_to_canonical_key).
- **performance_profile_expected**: `str` — Expected Broadcom performance_profile value (case-insensitive). Default RoCE.
- **support_rdma_disabled_values**: `List[str]` — Values that indicate RDMA is not supported (case-insensitive).
- **pcie_relaxed_ordering_expected**: `str` — Expected Broadcom pcie_relaxed_ordering value (e.g. 'Relaxed ordering = enabled'); checked case-insensitively. Default enabled.
- **expected_qos_prio_map**: `Optional[Dict[Any, Any]]` — Expected priority-to-TC map (e.g. {0: 0, 1: 1}; keys may be int or str in config). Checked per device when set.
- **expected_qos_pfc_enabled**: `Optional[int]` — Expected PFC enabled value (0/1 or bitmask). Checked per device when set.
- **expected_qos_tsa_map**: `Optional[Dict[Any, Any]]` — Expected TSA map for ETS (e.g. {0: 'ets', 1: 'strict'}; keys may be int or str in config). Checked per device when set.
- **expected_qos_tc_bandwidth**: `Optional[List[int]]` — Expected TC bandwidth percentages. Checked per device when set.
- **require_qos_consistent_across_adapters**: `bool` — When True and no expected_qos_* are set, require all adapters to have the same prio_map, pfc_enabled, and tsa_map.
- **nicctl_log_error_regex**: `Optional[List[Dict[str, Any]]]` — Optional list of error patterns for nicctl show card logs.

## Analyzer Args Class OsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/os/analyzer_args.py)

### Annotations / fields

- **exp_os**: `Union[str, list]` — Expected OS name/version string(s) to match (e.g. from lsb_release or /etc/os-release).
- **exact_match**: `bool` — If True, require exact match for exp_os; otherwise substring match.

## Analyzer Args Class PackageAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/package/analyzer_args.py)

### Annotations / fields

- **exp_package_ver**: `Dict[str, Optional[str]]` — Map package name -> expected version (None = any version). Checked against installed packages.
- **regex_match**: `bool` — If True, match package versions with regex; otherwise exact or prefix match.
- **rocm_regex**: `Optional[str]` — Optional regex to identify ROCm package version (used when enable_rocm_regex is True).
- **enable_rocm_regex**: `bool` — If True, use rocm_regex (or default pattern) to extract ROCm version for checks.

## Analyzer Args Class PcieAnalyzerArgs

### Description

Arguments for PCIe analyzer

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/pcie/analyzer_args.py)

### Annotations / fields

- **exp_speed**: `int` — Expected PCIe link speed (generation 1–5).
- **exp_width**: `int` — Expected PCIe link width in lanes (1–16).
- **exp_sriov_count**: `int` — Expected SR-IOV virtual function count.
- **exp_gpu_count_override**: `Optional[int]` — Override expected GPU count for validation.
- **exp_max_payload_size**: `Union[Dict[int, int], int, NoneType]` — Expected max payload size: int for all devices, or dict keyed by device ID.
- **exp_max_rd_req_size**: `Union[Dict[int, int], int, NoneType]` — Expected max read request size: int for all devices, or dict keyed by device ID.
- **exp_ten_bit_tag_req_en**: `Union[Dict[int, int], int, NoneType]` — Expected 10-bit tag request enable: int for all devices, or dict keyed by device ID.

## Analyzer Args Class ProcessAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/process/analyzer_args.py)

### Annotations / fields

- **max_kfd_processes**: `int` — Maximum allowed number of KFD (Kernel Fusion Driver) processes; 0 disables the check.
- **max_cpu_usage**: `float` — Maximum allowed CPU usage (percent) for process checks.

## Analyzer Args Class RocmAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/analyzer_args.py)

### Annotations / fields

- **exp_rocm**: `Union[str, list]` — Expected ROCm version string(s) to match (e.g. from rocminfo).
- **exp_rocm_latest**: `str` — Expected 'latest' ROCm path or version string for versioned installs.
- **exp_rocm_sub_versions**: `dict[str, Union[str, list]]` — Map sub-version name (e.g. version_rocm) to expected string or list of allowed strings.

## Analyzer Args Class SysSettingsAnalyzerArgs

### Description

Sysfs settings for analysis via a list of checks (path, expected values, name).

    The path in each check is the sysfs path to read; the collector uses these paths
    when collection_args is derived from analysis_args (e.g. by the plugin).

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sys_settings/analyzer_args.py)

### Annotations / fields

- **checks**: `Optional[list[nodescraper.plugins.inband.sys_settings.analyzer_args.SysfsCheck]]` — List of sysfs checks (path, expected values or pattern, display name).

## Analyzer Args Class SysctlAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sysctl/analyzer_args.py)

### Annotations / fields

- **exp_vm_swappiness**: `Optional[int]` — Expected vm.swappiness value.
- **exp_vm_numa_balancing**: `Optional[int]` — Expected vm.numa_balancing value.
- **exp_vm_oom_kill_allocating_task**: `Optional[int]` — Expected vm.oom_kill_allocating_task value.
- **exp_vm_compaction_proactiveness**: `Optional[int]` — Expected vm.compaction_proactiveness value.
- **exp_vm_compact_unevictable_allowed**: `Optional[int]` — Expected vm.compact_unevictable_allowed value.
- **exp_vm_extfrag_threshold**: `Optional[int]` — Expected vm.extfrag_threshold value.
- **exp_vm_zone_reclaim_mode**: `Optional[int]` — Expected vm.zone_reclaim_mode value.
- **exp_vm_dirty_background_ratio**: `Optional[int]` — Expected vm.dirty_background_ratio value.
- **exp_vm_dirty_ratio**: `Optional[int]` — Expected vm.dirty_ratio value.
- **exp_vm_dirty_writeback_centisecs**: `Optional[int]` — Expected vm.dirty_writeback_centisecs value.
- **exp_kernel_numa_balancing**: `Optional[int]` — Expected kernel.numa_balancing value.
