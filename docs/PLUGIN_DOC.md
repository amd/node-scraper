# Plugin Documentation

# Plugin Table

| Plugin | Collection | Analysis | DataModel | Collector | Analyzer |
| --- | --- | --- | --- | --- | --- |
| AmdSmiPlugin | amd-smi firmware --json<br>amd-smi list --json<br>amd-smi partition --json<br>amd-smi process --json<br>amd-smi static -g all --json<br>amd-smi version --json | **Analyzer Args:**<br>- `check_static_data`: bool<br>- `expected_gpu_processes`: Optional[int]<br>- `expected_max_power`: Optional[int]<br>- `expected_driver_version`: Optional[str]<br>- `expected_memory_partition_mode`: Optional[str]<br>- `expected_compute_partition_mode`: Optional[str]<br>- `expected_pldm_version`: Optional[str]<br>- `l0_to_recovery_count_error_threshold`: Optional[int]<br>- `l0_to_recovery_count_warning_threshold`: Optional[int]<br>- `vendorid_ep`: Optional[str]<br>- `vendorid_ep_vf`: Optional[str]<br>- `devid_ep`: Optional[str]<br>- `devid_ep_vf`: Optional[str]<br>- `sku_name`: Optional[str] | [AmdSmiDataModel](#AmdSmiDataModel-Model) | [AmdSmiCollector](#Collector-Class-AmdSmiCollector) | [AmdSmiAnalyzer](#Data-Analyzer-Class-AmdSmiAnalyzer) |
| BiosPlugin | sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'<br>wmic bios get SMBIOSBIOSVersion /Value | **Analyzer Args:**<br>- `exp_bios_version`: list[str]<br>- `regex_match`: bool | [BiosDataModel](#BiosDataModel-Model) | [BiosCollector](#Collector-Class-BiosCollector) | [BiosAnalyzer](#Data-Analyzer-Class-BiosAnalyzer) |
| CmdlinePlugin | cat /proc/cmdline | **Analyzer Args:**<br>- `required_cmdline`: Union[str, list]<br>- `banned_cmdline`: Union[str, list] | [CmdlineDataModel](#CmdlineDataModel-Model) | [CmdlineCollector](#Collector-Class-CmdlineCollector) | [CmdlineAnalyzer](#Data-Analyzer-Class-CmdlineAnalyzer) |
| DeviceEnumerationPlugin | lscpu \| grep Socket \| awk '{ print $2 }'<br>powershell -Command "(Get-WmiObject -Class Win32_Processor \| Measure-Object).Count"<br>lspci -d {vendorid_ep}: \| grep -i 'VGA\\|Display\\|3D' \| wc -l<br>powershell -Command "(wmic path win32_VideoController get name \| findstr AMD \| Measure-Object).Count"<br>lspci -d {vendorid_ep}: \| grep -i 'Virtual Function' \| wc -l<br>powershell -Command "(Get-VMHostPartitionableGpu \| Measure-Object).Count" | **Analyzer Args:**<br>- `cpu_count`: Optional[list[int]]<br>- `gpu_count`: Optional[list[int]]<br>- `vf_count`: Optional[list[int]] | [DeviceEnumerationDataModel](#DeviceEnumerationDataModel-Model) | [DeviceEnumerationCollector](#Collector-Class-DeviceEnumerationCollector) | [DeviceEnumerationAnalyzer](#Data-Analyzer-Class-DeviceEnumerationAnalyzer) |
| DimmPlugin | sh -c 'dmidecode -t 17 \| tr -s " " \| grep -v "Volatile\\|None\\|Module" \| grep Size' 2>/dev/null<br>wmic memorychip get Capacity | - | [DimmDataModel](#DimmDataModel-Model) | [DimmCollector](#Collector-Class-DimmCollector) | - |
| DkmsPlugin | dkms status<br>dkms --version | **Analyzer Args:**<br>- `dkms_status`: Union[str, list]<br>- `dkms_version`: Union[str, list]<br>- `regex_match`: bool | [DkmsDataModel](#DkmsDataModel-Model) | [DkmsCollector](#Collector-Class-DkmsCollector) | [DkmsAnalyzer](#Data-Analyzer-Class-DkmsAnalyzer) |
| DmesgPlugin | dmesg --time-format iso -x<br>ls -1 /var/log/dmesg* 2>/dev/null \| grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' \|\| true | **Built-in Regexes:**<br>- Out of memory error: `(?:oom_kill_process.*)\|(?:Out of memory.*)`<br>- I/O Page Fault: `IO_PAGE_FAULT`<br>- Kernel Panic: `\bkernel panic\b.*`<br>- SQ Interrupt: `sq_intr`<br>- SRAM ECC: `sram_ecc.*`<br>- Failed to load driver. IP hardware init error.: `\[amdgpu\]\] \*ERROR\* hw_init of IP block.*`<br>- Failed to load driver. IP software init error.: `\[amdgpu\]\] \*ERROR\* sw_init of IP block.*`<br>- Real Time throttling activated: `sched: RT throttling activated.*`<br>- RCU preempt detected stalls: `rcu_preempt detected stalls.*`<br>- RCU preempt self-detected stall: `rcu_preempt self-detected stall.*`<br>- QCM fence timeout: `qcm fence wait loop timeout.*`<br>- General protection fault: `(?:[\w-]+(?:\[[0-9.]+\])?\s+)?general protectio...`<br>- Segmentation fault: `(?:segfault.*in .*\[)\|(?:[Ss]egmentation [Ff]au...`<br>- Failed to disallow cf state: `amdgpu: Failed to disallow cf state.*`<br>- Failed to terminate tmr: `\*ERROR\* Failed to terminate tmr.*`<br>- Suspend of IP block failed: `\*ERROR\* suspend of IP block <\w+> failed.*`<br>- amdgpu Page Fault: `(amdgpu \w{4}:\w{2}:\w{2}\.\w:\s+amdgpu:\s+\[\S...`<br>- Page Fault: `page fault for address.*`<br>- Fatal error during GPU init: `(?:amdgpu)(.*Fatal error during GPU init)\|(Fata...`<br>- PCIe AER Error: `(?:pcieport )(.*AER: aer_status.*)\|(aer_status.*)`<br>- Failed to read journal file: `Failed to read journal file.*`<br>- Journal file corrupted or uncleanly shut down: `journal corrupted or uncleanly shut down.*`<br>- ACPI BIOS Error: `ACPI BIOS Error`<br>- ACPI Error: `ACPI Error`<br>- Filesystem corrupted!: `EXT4-fs error \(device .*\):`<br>- Error in buffered IO, check filesystem integrity: `(Buffer I\/O error on dev)(?:ice)? (\w+)`<br>- PCIe card no longer present: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`<br>- PCIe Link Down: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(Slot\(...`<br>- Mismatched clock configuration between PCIe device and host: `pcieport (\w+:\w+:\w+\.\w+):\s+(\w+):\s+(curren...`<br>- RAS Correctable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Uncorrectable Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Deferred Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- RAS Corrected PCIe Error: `((?:\[Hardware Error\]:\s+)?event severity: cor...`<br>- GPU Reset: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- GPU reset failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`<br>- ACA Error: `(Accelerator Check Architecture[^\n]*)(?:\n[^\n...`<br>- MCE Error: `\[Hardware Error\]:.+MC\d+_STATUS.*(?:\n.*){0,5}`<br>- Mode 2 Reset Failed: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)? (...`<br>- RAS Corrected Error: `(?:\d{4}-\d+-\d+T\d+:\d+:\d+,\d+[+-]\d+:\d+)?(....`<br>- SGX Error: `x86/cpu: SGX disabled by BIOS`<br>- GPU Throttled: `amdgpu \w{4}:\w{2}:\w{2}.\w: amdgpu: WARN: GPU ...`<br>- LNet: ko2iblnd has no matching interfaces: `(?:\[[^\]]+\]\s*)?LNetError:.*ko2iblnd:\s*No ma...`<br>- LNet: Error starting up LNI: `(?:\[[^\]]+\]\s*)?LNetError:\s*.*Error\s*-?\d+\...`<br>- Lustre: network initialisation failed: `LustreError:.*ptlrpc_init_portals\(\).*network ...` | [DmesgData](#DmesgData-Model) | [DmesgCollector](#Collector-Class-DmesgCollector) | [DmesgAnalyzer](#Data-Analyzer-Class-DmesgAnalyzer) |
| JournalPlugin | journalctl --no-pager --system --output=short-iso | - | [JournalData](#JournalData-Model) | [JournalCollector](#Collector-Class-JournalCollector) | - |
| KernelPlugin | sh -c 'uname -a'<br>wmic os get Version /Value | **Analyzer Args:**<br>- `exp_kernel`: Union[str, list]<br>- `regex_match`: bool | [KernelDataModel](#KernelDataModel-Model) | [KernelCollector](#Collector-Class-KernelCollector) | [KernelAnalyzer](#Data-Analyzer-Class-KernelAnalyzer) |
| KernelModulePlugin | cat /proc/modules<br>wmic os get Version /Value | **Analyzer Args:**<br>- `kernel_modules`: dict[str, dict]<br>- `regex_filter`: list[str] | [KernelModuleDataModel](#KernelModuleDataModel-Model) | [KernelModuleCollector](#Collector-Class-KernelModuleCollector) | [KernelModuleAnalyzer](#Data-Analyzer-Class-KernelModuleAnalyzer) |
| MemoryPlugin | free -b<br>wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value | - | [MemoryDataModel](#MemoryDataModel-Model) | [MemoryCollector](#Collector-Class-MemoryCollector) | [MemoryAnalyzer](#Data-Analyzer-Class-MemoryAnalyzer) |
| NvmePlugin | nvme smart-log {dev}<br>nvme error-log {dev} --log-entries=256<br>nvme id-ctrl {dev}<br>nvme id-ns {dev}{ns}<br>nvme fw-log {dev}<br>nvme self-test-log {dev}<br>nvme get-log {dev} --log-id=6 --log-len=512<br>nvme telemetry-log {dev} --output-file={dev}_{f_name} | - | [NvmeDataModel](#NvmeDataModel-Model) | [NvmeCollector](#Collector-Class-NvmeCollector) | - |
| OsPlugin | sh -c '( lsb_release -ds \|\| (cat /etc/*release \| grep PRETTY_NAME) \|\| uname -om ) 2>/dev/null \| head -n1'<br>cat /etc/*release \| grep VERSION_ID<br>wmic os get Version /value<br>wmic os get Caption /Value | **Analyzer Args:**<br>- `exp_os`: Union[str, list]<br>- `exact_match`: bool | [OsDataModel](#OsDataModel-Model) | [OsCollector](#Collector-Class-OsCollector) | [OsAnalyzer](#Data-Analyzer-Class-OsAnalyzer) |
| PackagePlugin | dnf list --installed<br>dpkg-query -W<br>pacman -Q<br>cat /etc/*release<br>wmic product get name,version | **Analyzer Args:**<br>- `exp_package_ver`: Dict[str, Optional[str]]<br>- `regex_match`: bool | [PackageDataModel](#PackageDataModel-Model) | [PackageCollector](#Collector-Class-PackageCollector) | [PackageAnalyzer](#Data-Analyzer-Class-PackageAnalyzer) |
| PciePlugin | lspci -d {vendor_id}: -nn<br>lspci -x<br>lspci -xxxx<br>lspci -PP<br>lspci -PP -d {vendor_id}:{dev_id}<br>lspci -vt<br>lspci -vvv | **Analyzer Args:**<br>- `exp_speed`: int<br>- `exp_width`: int<br>- `exp_sriov_count`: int<br>- `exp_gpu_count_override`: Optional[int]<br>- `exp_max_payload_size`: Union[Dict[int, int], int, NoneType]<br>- `exp_max_rd_req_size`: Union[Dict[int, int], int, NoneType]<br>- `exp_ten_bit_tag_req_en`: Union[Dict[int, int], int, NoneType] | [PcieDataModel](#PcieDataModel-Model) | [PcieCollector](#Collector-Class-PcieCollector) | [PcieAnalyzer](#Data-Analyzer-Class-PcieAnalyzer) |
| ProcessPlugin | top -b -n 1<br>rocm-smi --showpids<br>top -b -n 1 -o %CPU  | **Analyzer Args:**<br>- `max_kfd_processes`: int<br>- `max_cpu_usage`: float | [ProcessDataModel](#ProcessDataModel-Model) | [ProcessCollector](#Collector-Class-ProcessCollector) | [ProcessAnalyzer](#Data-Analyzer-Class-ProcessAnalyzer) |
| RocmPlugin | {rocm_path}/opencl/bin/*/clinfo<br>env \| grep -Ei 'rocm\|hsa\|hip\|mpi\|openmp\|ucx\|miopen'<br>ls /sys/class/kfd/kfd/proc/<br>grep -i -E 'rocm' /etc/ld.so.conf.d/*<br>{rocm_path}/bin/rocminfo<br>ls -v -d /opt/rocm*<br>ls -v -d /opt/rocm-[3-7]* \| tail -1<br>ldconfig -p \| grep -i -E 'rocm'<br>/opt/rocm/.info/version-rocm<br>/opt/rocm/.info/version | **Analyzer Args:**<br>- `exp_rocm`: Union[str, list]<br>- `exp_rocm_latest`: str | [RocmDataModel](#RocmDataModel-Model) | [RocmCollector](#Collector-Class-RocmCollector) | [RocmAnalyzer](#Data-Analyzer-Class-RocmAnalyzer) |
| StoragePlugin | sh -c 'df -lH -B1 \| grep -v 'boot''<br>wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace | - | [StorageDataModel](#StorageDataModel-Model) | [StorageCollector](#Collector-Class-StorageCollector) | [StorageAnalyzer](#Data-Analyzer-Class-StorageAnalyzer) |
| SysctlPlugin | sysctl -n | **Analyzer Args:**<br>- `exp_vm_swappiness`: Optional[int]<br>- `exp_vm_numa_balancing`: Optional[int]<br>- `exp_vm_oom_kill_allocating_task`: Optional[int]<br>- `exp_vm_compaction_proactiveness`: Optional[int]<br>- `exp_vm_compact_unevictable_allowed`: Optional[int]<br>- `exp_vm_extfrag_threshold`: Optional[int]<br>- `exp_vm_zone_reclaim_mode`: Optional[int]<br>- `exp_vm_dirty_background_ratio`: Optional[int]<br>- `exp_vm_dirty_ratio`: Optional[int]<br>- `exp_vm_dirty_writeback_centisecs`: Optional[int]<br>- `exp_kernel_numa_balancing`: Optional[int] | [SysctlDataModel](#SysctlDataModel-Model) | [SysctlCollector](#Collector-Class-SysctlCollector) | [SysctlAnalyzer](#Data-Analyzer-Class-SysctlAnalyzer) |
| SyslogPlugin | ls -1 /var/log/syslog* 2>/dev/null \| grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' \|\| true | - | [SyslogData](#SyslogData-Model) | [SyslogCollector](#Collector-Class-SyslogCollector) | - |
| UptimePlugin | uptime | - | [UptimeDataModel](#UptimeDataModel-Model) | [UptimeCollector](#Collector-Class-UptimeCollector) | - |

# Collectors

## Collector Class AmdSmiCollector

### Description

Class for collection of inband tool amd-smi data.

**Bases**: ['InBandDataCollector']

**Link to code**: [amdsmi_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/amdsmi/amdsmi_collector.py)

### Class Variables

- **AMD_SMI_EXE**: `amd-smi`
- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_VERSION**: `amd-smi version --json`
- **CMD_LIST**: `amd-smi list --json`
- **CMD_PROCESS**: `amd-smi process --json`
- **CMD_PARTITION**: `amd-smi partition --json`
- **CMD_FIRMWARE**: `amd-smi firmware --json`
- **CMD_STATIC**: `amd-smi static -g all --json`

### Provides Data

AmdSmiDataModel

### Commands

- amd-smi firmware --json
- amd-smi list --json
- amd-smi partition --json
- amd-smi process --json
- amd-smi static -g all --json
- amd-smi version --json

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

- **CMD_CPU_COUNT_LINUX**: `lscpu | grep Socket | awk '{ print $2 }'`
- **CMD_GPU_COUNT_LINUX**: `lspci -d {vendorid_ep}: | grep -i 'VGA\|Display\|3D' | wc -l`
- **CMD_VF_COUNT_LINUX**: `lspci -d {vendorid_ep}: | grep -i 'Virtual Function' | wc -l`
- **CMD_CPU_COUNT_WINDOWS**: `powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"`
- **CMD_GPU_COUNT_WINDOWS**: `powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"`
- **CMD_VF_COUNT_WINDOWS**: `powershell -Command "(Get-VMHostPartitionableGpu | Measure-Object).Count"`

### Provides Data

DeviceEnumerationDataModel

### Commands

- lscpu | grep Socket | awk '{ print $2 }'
- powershell -Command "(Get-WmiObject -Class Win32_Processor | Measure-Object).Count"
- lspci -d {vendorid_ep}: | grep -i 'VGA\|Display\|3D' | wc -l
- powershell -Command "(wmic path win32_VideoController get name | findstr AMD | Measure-Object).Count"
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

### Provides Data

DimmDataModel

### Commands

- sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\|None\|Module" | grep Size' 2>/dev/null
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

## Collector Class JournalCollector

### Description

Read journal log via journalctl.

**Bases**: ['InBandDataCollector']

**Link to code**: [journal_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/journal_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `journalctl --no-pager --system --output=short-iso`

### Provides Data

JournalData

### Commands

- journalctl --no-pager --system --output=short-iso

## Collector Class KernelCollector

### Description

Read kernel version

**Bases**: ['InBandDataCollector']

**Link to code**: [kernel_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/kernel_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic os get Version /Value`
- **CMD**: `sh -c 'uname -a'`

### Provides Data

KernelDataModel

### Commands

- sh -c 'uname -a'
- wmic os get Version /Value

## Collector Class KernelModuleCollector

### Description

Read kernel modules and associated parameters

**Bases**: ['InBandDataCollector']

**Link to code**: [kernel_module_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/kernel_module_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic os get Version /Value`
- **CMD**: `cat /proc/modules`

### Provides Data

KernelModuleDataModel

### Commands

- cat /proc/modules
- wmic os get Version /Value

## Collector Class MemoryCollector

### Description

Collect memory usage details

**Bases**: ['InBandDataCollector']

**Link to code**: [memory_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/memory_collector.py)

### Class Variables

- **CMD_WINDOWS**: `wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value`
- **CMD**: `free -b`

### Provides Data

MemoryDataModel

### Commands

- free -b
- wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value

## Collector Class NvmeCollector

### Description

Collect NVMe details from the system.

**Bases**: ['InBandDataCollector']

**Link to code**: [nvme_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nvme/nvme_collector.py)

### Class Variables

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
    - `lspci -vt`: Tree view of PCIe data
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
- **CMD_LSPCI_TREE**: `lspci -vt`
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
- lspci -vt
- lspci -vvv

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

## Collector Class RocmCollector

### Description

Collect ROCm version data

**Bases**: ['InBandDataCollector']

**Link to code**: [rocm_collector.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocm_collector.py)

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_VERSION_PATHS**: `['/opt/rocm/.info/version-rocm', '/opt/rocm/.info/version']`
- **CMD_ROCMINFO**: `{rocm_path}/bin/rocminfo`
- **CMD_ROCM_LATEST**: `ls -v -d /opt/rocm-[3-7]* | tail -1`
- **CMD_ROCM_DIRS**: `ls -v -d /opt/rocm*`
- **CMD_LD_CONF**: `grep -i -E 'rocm' /etc/ld.so.conf.d/*`
- **CMD_ROCM_LIBS**: `ldconfig -p | grep -i -E 'rocm'`
- **CMD_ENV_VARS**: `env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'`
- **CMD_CLINFO**: `{rocm_path}/opencl/bin/*/clinfo`
- **CMD_KFD_PROC**: `ls /sys/class/kfd/kfd/proc/`

### Provides Data

RocmDataModel

### Commands

- {rocm_path}/opencl/bin/*/clinfo
- env | grep -Ei 'rocm|hsa|hip|mpi|openmp|ucx|miopen'
- ls /sys/class/kfd/kfd/proc/
- grep -i -E 'rocm' /etc/ld.so.conf.d/*
- {rocm_path}/bin/rocminfo
- ls -v -d /opt/rocm*
- ls -v -d /opt/rocm-[3-7]* | tail -1
- ldconfig -p | grep -i -E 'rocm'
- /opt/rocm/.info/version-rocm
- /opt/rocm/.info/version

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
- **firmware**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.Fw]]`
- **bad_pages**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.BadPages]]`
- **static**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiStatic]]`
- **metric**: `Optional[list[nodescraper.plugins.inband.amdsmi.amdsmidata.AmdSmiMetric]]`

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

## JournalData Model

### Description

Data model for journal logs

**Link to code**: [journaldata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/journal/journaldata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **journal_log**: `str`

## KernelDataModel Model

**Link to code**: [kerneldata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/kerneldata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_info**: `str`
- **kernel_version**: `str`

## KernelModuleDataModel Model

**Link to code**: [kernel_module_data.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/kernel_module_data.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_modules**: `dict`

## MemoryDataModel Model

**Link to code**: [memorydata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/memory/memorydata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **mem_free**: `str`
- **mem_total**: `str`

## NvmeDataModel Model

**Link to code**: [nvmedata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/nvme/nvmedata.py)

**Bases**: ['DataModel']

### Model annotations and fields

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

## RocmDataModel Model

**Link to code**: [rocmdata.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocmdata.py)

**Bases**: ['DataModel']

### Model annotations and fields

- **rocm_version**: `str`
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

**Bases**: ['DataAnalyzer']

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
  regex=re.compile('(?:pcieport )(.*AER: aer_status.*)|(aer_status.*)') message='PCIe AER Error' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.ERROR: 3>,
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
  regex=re.compile('amdgpu \\w{4}:\\w{2}:\\w{2}.\\w: amdgpu: WARN: GPU is throttled.*') message='GPU Throttled' event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:.*ko2iblnd:\\s*No matching interfaces', re.IGNORECASE) message='LNet: ko2iblnd has no matching interfaces' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:\\s*.*Error\\s*-?\\d+\\s+starting up LNI\\s+\\w+', re.IGNORECASE) message='LNet: Error starting up LNI' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>,
  regex=re.compile('LustreError:.*ptlrpc_init_portals\\(\\).*network initiali[sz]ation failed', re.IGNORECASE) message='Lustre: network initialisation failed' event_category=<EventCategory.IO: 'IO'> event_priority=<EventPriority.WARNING: 2>
]`

### Regex Patterns

*46 items defined*

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
- - PCIe AER Error: `(?:pcieport )(.*AER: aer_status.*)|(aer_status.*)`
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
- - GPU Throttled: `amdgpu \w{4}:\w{2}:\w{2}.\w: amdgpu: WARN: GPU ...`
- - LNet: ko2iblnd has no matching interfaces: `(?:\[[^\]]+\]\s*)?LNetError:.*ko2iblnd:\s*No ma...`
- - LNet: Error starting up LNI: `(?:\[[^\]]+\]\s*)?LNetError:\s*.*Error\s*-?\d+\...`
- - Lustre: network initialisation failed: `LustreError:.*ptlrpc_init_portals\(\).*network ...`

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

## Data Analyzer Class RocmAnalyzer

### Description

Check ROCm matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: [rocm_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/rocm_analyzer.py)

## Data Analyzer Class StorageAnalyzer

### Description

Check storage usage

**Bases**: ['DataAnalyzer']

**Link to code**: [storage_analyzer.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/storage/storage_analyzer.py)

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

- **check_static_data**: `bool`
- **expected_gpu_processes**: `Optional[int]`
- **expected_max_power**: `Optional[int]`
- **expected_driver_version**: `Optional[str]`
- **expected_memory_partition_mode**: `Optional[str]`
- **expected_compute_partition_mode**: `Optional[str]`
- **expected_pldm_version**: `Optional[str]`
- **l0_to_recovery_count_error_threshold**: `Optional[int]`
- **l0_to_recovery_count_warning_threshold**: `Optional[int]`
- **vendorid_ep**: `Optional[str]`
- **vendorid_ep_vf**: `Optional[str]`
- **devid_ep**: `Optional[str]`
- **devid_ep_vf**: `Optional[str]`
- **sku_name**: `Optional[str]`

## Analyzer Args Class BiosAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/bios/analyzer_args.py)

### Annotations / fields

- **exp_bios_version**: `list[str]`
- **regex_match**: `bool`

## Analyzer Args Class CmdlineAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/cmdline/analyzer_args.py)

### Annotations / fields

- **required_cmdline**: `Union[str, list]`
- **banned_cmdline**: `Union[str, list]`

## Analyzer Args Class DeviceEnumerationAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/device_enumeration/analyzer_args.py)

### Annotations / fields

- **cpu_count**: `Optional[list[int]]`
- **gpu_count**: `Optional[list[int]]`
- **vf_count**: `Optional[list[int]]`

## Analyzer Args Class DkmsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/dkms/analyzer_args.py)

### Annotations / fields

- **dkms_status**: `Union[str, list]`
- **dkms_version**: `Union[str, list]`
- **regex_match**: `bool`

## Analyzer Args Class KernelAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel/analyzer_args.py)

### Annotations / fields

- **exp_kernel**: `Union[str, list]`
- **regex_match**: `bool`

## Analyzer Args Class KernelModuleAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/kernel_module/analyzer_args.py)

### Annotations / fields

- **kernel_modules**: `dict[str, dict]`
- **regex_filter**: `list[str]`

## Analyzer Args Class OsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/os/analyzer_args.py)

### Annotations / fields

- **exp_os**: `Union[str, list]`
- **exact_match**: `bool`

## Analyzer Args Class PackageAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/package/analyzer_args.py)

### Annotations / fields

- **exp_package_ver**: `Dict[str, Optional[str]]`
- **regex_match**: `bool`

## Analyzer Args Class PcieAnalyzerArgs

### Description

Arguments for PCIe analyzer

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/pcie/analyzer_args.py)

### Annotations / fields

- **exp_speed**: `int`
- **exp_width**: `int`
- **exp_sriov_count**: `int`
- **exp_gpu_count_override**: `Optional[int]`
- **exp_max_payload_size**: `Union[Dict[int, int], int, NoneType]`
- **exp_max_rd_req_size**: `Union[Dict[int, int], int, NoneType]`
- **exp_ten_bit_tag_req_en**: `Union[Dict[int, int], int, NoneType]`

## Analyzer Args Class ProcessAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/process/analyzer_args.py)

### Annotations / fields

- **max_kfd_processes**: `int`
- **max_cpu_usage**: `float`

## Analyzer Args Class RocmAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/rocm/analyzer_args.py)

### Annotations / fields

- **exp_rocm**: `Union[str, list]`
- **exp_rocm_latest**: `str`

## Analyzer Args Class SysctlAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: [analyzer_args.py](https://github.com/amd/node-scraper/blob/HEAD/nodescraper/plugins/inband/sysctl/analyzer_args.py)

### Annotations / fields

- **exp_vm_swappiness**: `Optional[int]`
- **exp_vm_numa_balancing**: `Optional[int]`
- **exp_vm_oom_kill_allocating_task**: `Optional[int]`
- **exp_vm_compaction_proactiveness**: `Optional[int]`
- **exp_vm_compact_unevictable_allowed**: `Optional[int]`
- **exp_vm_extfrag_threshold**: `Optional[int]`
- **exp_vm_zone_reclaim_mode**: `Optional[int]`
- **exp_vm_dirty_background_ratio**: `Optional[int]`
- **exp_vm_dirty_ratio**: `Optional[int]`
- **exp_vm_dirty_writeback_centisecs**: `Optional[int]`
- **exp_kernel_numa_balancing**: `Optional[int]`
