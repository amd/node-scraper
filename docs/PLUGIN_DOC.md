# Plugin Documentation

# Plugin Table

| Plugin | DataModel | Collector | Analyzer | AnalyzerArgs | Cmd(s) |
| --- | --- | --- | --- | --- | --- |
| nodescraper.plugins.inband.bios.bios_plugin.BiosPlugin | [BiosDataModel](#BiosDataModel-Model) | [BiosCollector](#Collector-Class-BiosCollector) | [BiosAnalyzer](#Data-Analyzer-Class-BiosAnalyzer) | BiosAnalyzerArgs | sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'<br>wmic bios get SMBIOSBIOSVersion /Value |
| nodescraper.plugins.inband.cmdline.cmdline_plugin.CmdlinePlugin | [CmdlineDataModel](#CmdlineDataModel-Model) | [CmdlineCollector](#Collector-Class-CmdlineCollector) | [CmdlineAnalyzer](#Data-Analyzer-Class-CmdlineAnalyzer) | CmdlineAnalyzerArgs | cat /proc/cmdline |
| nodescraper.plugins.inband.dimm.dimm_plugin.DimmPlugin | [DimmDataModel](#DimmDataModel-Model) | [DimmCollector](#Collector-Class-DimmCollector) | - | - | sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\|None\|Module" | grep Size' 2>/dev/null<br>wmic memorychip get Capacity |
| nodescraper.plugins.inband.dkms.dkms_plugin.DkmsPlugin | [DkmsDataModel](#DkmsDataModel-Model) | [DkmsCollector](#Collector-Class-DkmsCollector) | [DkmsAnalyzer](#Data-Analyzer-Class-DkmsAnalyzer) | DkmsAnalyzerArgs | dkms status<br>dkms --version |
| nodescraper.plugins.inband.dmesg.dmesg_plugin.DmesgPlugin | [DmesgData](#DmesgData-Model) | [DmesgCollector](#Collector-Class-DmesgCollector) | [DmesgAnalyzer](#Data-Analyzer-Class-DmesgAnalyzer) | - | dmesg --time-format iso -x<br>ls -1 /var/log/dmesg* 2>/dev/null | grep -E '^/var/log/dmesg(\.[0-9]+(\.gz)?)?$' || true |
| nodescraper.plugins.inband.journal.journal_plugin.JournalPlugin | [JournalData](#JournalData-Model) | [JournalCollector](#Collector-Class-JournalCollector) | - | - | journalctl --no-pager --system --output=short-iso |
| nodescraper.plugins.inband.kernel.kernel_plugin.KernelPlugin | [KernelDataModel](#KernelDataModel-Model) | [KernelCollector](#Collector-Class-KernelCollector) | [KernelAnalyzer](#Data-Analyzer-Class-KernelAnalyzer) | KernelAnalyzerArgs | sh -c 'uname -r'<br>wmic os get Version /Value |
| nodescraper.plugins.inband.kernel_module.kernel_module_plugin.KernelModulePlugin | [KernelModuleDataModel](#KernelModuleDataModel-Model) | [KernelModuleCollector](#Collector-Class-KernelModuleCollector) | [KernelModuleAnalyzer](#Data-Analyzer-Class-KernelModuleAnalyzer) | KernelModuleAnalyzerArgs | cat /proc/modules<br>wmic os get Version /Value |
| nodescraper.plugins.inband.memory.memory_plugin.MemoryPlugin | [MemoryDataModel](#MemoryDataModel-Model) | [MemoryCollector](#Collector-Class-MemoryCollector) | [MemoryAnalyzer](#Data-Analyzer-Class-MemoryAnalyzer) | - | free -b<br>wmic OS get FreePhysicalMemory /Value; wmic ComputerSystem get TotalPhysicalMemory /Value |
| nodescraper.plugins.inband.nvme.nvme_plugin.NvmePlugin | [NvmeDataModel](#NvmeDataModel-Model) | [NvmeCollector](#Collector-Class-NvmeCollector) | - | - | - |
| nodescraper.plugins.inband.os.os_plugin.OsPlugin | [OsDataModel](#OsDataModel-Model) | [OsCollector](#Collector-Class-OsCollector) | [OsAnalyzer](#Data-Analyzer-Class-OsAnalyzer) | OsAnalyzerArgs | sh -c '( lsb_release -ds || (cat /etc/*release | grep PRETTY_NAME) || uname -om ) 2>/dev/null | head -n1'<br>cat /etc/*release | grep VERSION_ID<br>wmic os get Version /value<br>wmic os get Caption /Value |
| nodescraper.plugins.inband.package.package_plugin.PackagePlugin | [PackageDataModel](#PackageDataModel-Model) | [PackageCollector](#Collector-Class-PackageCollector) | [PackageAnalyzer](#Data-Analyzer-Class-PackageAnalyzer) | PackageAnalyzerArgs | dnf list --installed<br>dpkg-query -W<br>pacman -Q<br>cat /etc/*release<br>wmic product get name,version |
| nodescraper.plugins.inband.process.process_plugin.ProcessPlugin | [ProcessDataModel](#ProcessDataModel-Model) | [ProcessCollector](#Collector-Class-ProcessCollector) | [ProcessAnalyzer](#Data-Analyzer-Class-ProcessAnalyzer) | ProcessAnalyzerArgs | top -b -n 1<br>rocm-smi --showpids<br>top -b -n 1 -o %CPU  |
| nodescraper.plugins.inband.rocm.rocm_plugin.RocmPlugin | [RocmDataModel](#RocmDataModel-Model) | [RocmCollector](#Collector-Class-RocmCollector) | [RocmAnalyzer](#Data-Analyzer-Class-RocmAnalyzer) | RocmAnalyzerArgs | /opt/rocm/.info/version-rocm<br>/opt/rocm/.info/version |
| nodescraper.plugins.inband.storage.storage_plugin.StoragePlugin | [StorageDataModel](#StorageDataModel-Model) | [StorageCollector](#Collector-Class-StorageCollector) | [StorageAnalyzer](#Data-Analyzer-Class-StorageAnalyzer) | - | sh -c 'df -lH -B1 | grep -v 'boot''<br>wmic LogicalDisk Where DriveType="3" Get DeviceId,Size,FreeSpace |
| nodescraper.plugins.inband.sysctl.sysctl_plugin.SysctlPlugin | [SysctlDataModel](#SysctlDataModel-Model) | [SysctlCollector](#Collector-Class-SysctlCollector) | [SysctlAnalyzer](#Data-Analyzer-Class-SysctlAnalyzer) | SysctlAnalyzerArgs | sysctl -n |
| nodescraper.plugins.inband.syslog.syslog_plugin.SyslogPlugin | [SyslogData](#SyslogData-Model) | [SyslogCollector](#Collector-Class-SyslogCollector) | - | - | ls -1 /var/log/syslog* 2>/dev/null | grep -E '^/var/log/syslog(\.[0-9]+(\.gz)?)?$' || true |
| nodescraper.plugins.inband.uptime.uptime_plugin.UptimePlugin | [UptimeDataModel](#UptimeDataModel-Model) | [UptimeCollector](#Collector-Class-UptimeCollector) | - | - | uptime |

# Collectors

## Collector Class BiosCollector

### Description

Collect BIOS details

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/bios/bios_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/cmdline/cmdline_collector.py

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `cat /proc/cmdline`

### Provides Data

CmdlineDataModel

### Commands

- cat /proc/cmdline

## Collector Class DimmCollector

### Description

Collect data on installed DIMMs

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/dimm/dimm_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/dkms/dkms_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/dmesg/dmesg_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/journal/journal_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/kernel/kernel_collector.py

### Class Variables

- **CMD_WINDOWS**: `wmic os get Version /Value`
- **CMD**: `sh -c 'uname -r'`

### Provides Data

KernelDataModel

### Commands

- sh -c 'uname -r'
- wmic os get Version /Value

## Collector Class KernelModuleCollector

### Description

Read kernel modules and associated parameters

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/kernel_module/kernel_module_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/memory/memory_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/nvme/nvme_collector.py

### Provides Data

NvmeDataModel

## Collector Class OsCollector

### Description

Collect OS details

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/os/os_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/package/package_collector.py

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

## Collector Class ProcessCollector

### Description

Collect Process details

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/process/process_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/rocm/rocm_collector.py

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD_VERSION_PATHS**: `['/opt/rocm/.info/version-rocm', '/opt/rocm/.info/version']`

### Provides Data

RocmDataModel

### Commands

- /opt/rocm/.info/version-rocm
- /opt/rocm/.info/version

## Collector Class StorageCollector

### Description

Collect disk usage details

**Bases**: ['InBandDataCollector']

**Link to code**: ../nodescraper/plugins/inband/storage/storage_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/sysctl/sysctl_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/syslog/syslog_collector.py

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

**Link to code**: ../nodescraper/plugins/inband/uptime/uptime_collector.py

### Class Variables

- **SUPPORTED_OS_FAMILY**: `{<OSFamily.LINUX: 3>}`
- **CMD**: `uptime`

### Provides Data

UptimeDataModel

### Commands

- uptime

# Data Models

## BiosDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/bios/biosdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **bios_version**: `<class 'str'>`

## CmdlineDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/cmdline/cmdlinedata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **cmdline**: `<class 'str'>`

## DimmDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/dimm/dimmdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **dimms**: `<class 'str'>`

## DkmsDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/dkms/dkmsdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **status**: `typing.Optional[str]`
- **version**: `typing.Optional[str]`

## DmesgData Model

### Description

Data model for in band dmesg log

**Link to code**: ../nodescraper/plugins/inband/dmesg/dmesgdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **dmesg_content**: `<class 'str'>`

## JournalData Model

### Description

Data model for journal logs

**Link to code**: ../nodescraper/plugins/inband/journal/journaldata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **journal_log**: `<class 'str'>`

## KernelDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/kernel/kerneldata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_version**: `<class 'str'>`

## KernelModuleDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/kernel_module/kernel_module_data.py

**Bases**: ['DataModel']

### Model annotations and fields

- **kernel_modules**: `<class 'dict'>`

## MemoryDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/memory/memorydata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **mem_free**: `<class 'str'>`
- **mem_total**: `<class 'str'>`

## NvmeDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/nvme/nvmedata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **devices**: `dict[str, nodescraper.plugins.inband.nvme.nvmedata.DeviceNvmeData]`

## OsDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/os/osdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **os_name**: `<class 'str'>`
- **os_version**: `<class 'str'>`

## PackageDataModel Model

### Description

Pacakge data contains the package data for the system

**Link to code**: ../nodescraper/plugins/inband/package/packagedata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **version_info**: `dict[str, str]`

## ProcessDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/process/processdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **kfd_process**: `typing.Optional[int]`
- **cpu_usage**: `typing.Optional[float]`
- **processes**: `typing.Optional[list[tuple[str, str]]]`

## RocmDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/rocm/rocmdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **rocm_version**: `<class 'str'>`

## StorageDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/storage/storagedata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **storage_data**: `dict[str, nodescraper.plugins.inband.storage.storagedata.DeviceStorageData]`

## SysctlDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/sysctl/sysctldata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **vm_swappiness**: `typing.Optional[int]`
- **vm_numa_balancing**: `typing.Optional[int]`
- **vm_oom_kill_allocating_task**: `typing.Optional[int]`
- **vm_compaction_proactiveness**: `typing.Optional[int]`
- **vm_compact_unevictable_allowed**: `typing.Optional[int]`
- **vm_extfrag_threshold**: `typing.Optional[int]`
- **vm_zone_reclaim_mode**: `typing.Optional[int]`
- **vm_dirty_background_ratio**: `typing.Optional[int]`
- **vm_dirty_ratio**: `typing.Optional[int]`
- **vm_dirty_writeback_centisecs**: `typing.Optional[int]`
- **kernel_numa_balancing**: `typing.Optional[int]`

## SyslogData Model

### Description

Data model for in band syslog logs

**Link to code**: ../nodescraper/plugins/inband/syslog/syslogdata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **syslog_logs**: `list[nodescraper.connection.inband.inband.TextFileArtifact]`

## UptimeDataModel Model

### Description

Base class for data model, used to define structure of data collected from the system

**Link to code**: ../nodescraper/plugins/inband/uptime/uptimedata.py

**Bases**: ['DataModel']

### Model annotations and fields

- **current_time**: `<class 'str'>`
- **uptime**: `<class 'str'>`

# Data Analyzers

## Data Analyzer Class BiosAnalyzer

### Description

Check bios matches expected bios details

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/bios/bios_analyzer.py

### Required Data

-

## Data Analyzer Class CmdlineAnalyzer

### Description

Check cmdline matches expected kernel cmdline

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/cmdline/cmdline_analyzer.py

### Required Data

-

## Data Analyzer Class DkmsAnalyzer

### Description

Check dkms matches expected status and version

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/dkms/dkms_analyzer.py

### Required Data

-

## Data Analyzer Class DmesgAnalyzer

### Description

Check dmesg for errors

**Bases**: ['RegexAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/dmesg/dmesg_analyzer.py

### Class Variables

- **ERROR_REGEX**: `[ErrorRegex(regex=re.compile('(?:oom_kill_process.*)|(?:Out of memory.*)'), message='Out of memory error', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('IO_PAGE_FAULT'), message='I/O Page Fault', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\bkernel panic\\b.*', re.IGNORECASE), message='Kernel Panic', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('sq_intr'), message='SQ Interrupt', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('sram_ecc.*'), message='SRAM ECC', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\[amdgpu\\]\\] \\*ERROR\\* hw_init of IP block.*'), message='Failed to load driver. IP hardware init error.', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\[amdgpu\\]\\] \\*ERROR\\* sw_init of IP block.*'), message='Failed to load driver. IP software init error.', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('sched: RT throttling activated.*'), message='Real Time throttling activated', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('rcu_preempt detected stalls.*'), message='RCU preempt detected stalls', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('rcu_preempt self-detected stall.*'), message='RCU preempt self-detected stall', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('qcm fence wait loop timeout.*'), message='QCM fence timeout', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:[\\w-]+(?:\\[[0-9.]+\\])?\\s+)?general protection fault[^\\n]*'), message='General protection fault', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:segfault.*in .*\\[)|(?:[Ss]egmentation [Ff]ault.*)|(?:[Ss]egfault.*)'), message='Segmentation fault', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('amdgpu: Failed to disallow cf state.*'), message='Failed to disallow cf state', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\*ERROR\\* Failed to terminate tmr.*'), message='Failed to terminate tmr', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\*ERROR\\* suspend of IP block <\\w+> failed.*'), message='Suspend of IP block failed', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(amdgpu \\w{4}:\\w{2}:\\w{2}\\.\\w:\\s+amdgpu:\\s+\\[\\S+\\]\\s*(?:retry|no-retry)? page fault[^\\n]*)(?:\\n[^\\n]*(amdgpu \\w{4}:\\w{2}:\\w{2}\\.\\w:\\s+amdgpu:[^\\n]*))?(?:\\n[^\\n]*(amdgpu \\w{4}:, re.MULTILINE), message='amdgpu Page Fault', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('page fault for address.*'), message='Page Fault', event_category=<EventCategory.OS: 'OS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:amdgpu)(.*Fatal error during GPU init)|(Fatal error during GPU init)'), message='Fatal error during GPU init', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:pcieport )(.*AER: aer_status.*)|(aer_status.*)'), message='PCIe AER Error', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('Failed to read journal file.*'), message='Failed to read journal file', event_category=<EventCategory.OS: 'OS'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('journal corrupted or uncleanly shut down.*'), message='Journal file corrupted or uncleanly shut down', event_category=<EventCategory.OS: 'OS'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('ACPI BIOS Error'), message='ACPI BIOS Error', event_category=<EventCategory.BIOS: 'BIOS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('ACPI Error'), message='ACPI Error', event_category=<EventCategory.BIOS: 'BIOS'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('EXT4-fs error \\(device .*\\):'), message='Filesystem corrupted!', event_category=<EventCategory.OS: 'OS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(Buffer I\\/O error on dev)(?:ice)? (\\w+)'), message='Error in buffered IO, check filesystem integrity', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(Slot\\(\\d+\\)):\\s+(Card not present)'), message='PCIe card no longer present', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(Slot\\(\\d+\\)):\\s+(Link Down)'), message='PCIe Link Down', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('pcieport (\\w+:\\w+:\\w+\\.\\w+):\\s+(\\w+):\\s+(current common clock configuration is inconsistent, reconfiguring)'), message='Mismatched clock configuration between PCIe device and host', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* correctable hardware errors detected in total in \\w+ block.*)'), message='RAS Correctable Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* uncorrectable hardware errors detected in \\w+ block.*)'), message='RAS Uncorrectable Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.* deferred hardware errors detected in \\w+ block.*)'), message='RAS Deferred Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('((?:\\[Hardware Error\\]:\\s+)?event severity: corrected.*)\\n.*(\\[Hardware Error\\]:\\s+Error \\d+, type: corrected.*)\\n.*(\\[Hardware Error\\]:\\s+section_type: PCIe error.*)'), message='RAS Corrected PCIe Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*GPU reset begin.*)'), message='GPU Reset', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*GPU reset(?:\\(\\d+\\))? failed.*)'), message='GPU reset failed', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(Accelerator Check Architecture[^\\n]*)(?:\\n[^\\n]*){0,10}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*entry\\[\\d+\\]\\.STATUS=0x[0-9a-fA-F]+)(?:\\n[^\\n]*){0,5}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*entry\\[\\d+\\], re.MULTILINE), message='ACA Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(Accelerator Check Architecture[^\\n]*)(?:\\n[^\\n]*){0,10}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*CONTROL=0x[0-9a-fA-F]+)(?:\\n[^\\n]*){0,5}?(amdgpu[ 0-9a-fA-F:.]+:? [^\\n]*STATUS=0x[0-9a-fA-F]+)(?:\\n[^\\, re.MULTILINE), message='ACA Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('\\[Hardware Error\\]:.+MC\\d+_STATUS.*(?:\\n.*){0,5}'), message='MCE Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)? (.*Mode2 reset failed.*)'), message='Mode 2 Reset Failed', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('(?:\\d{4}-\\d+-\\d+T\\d+:\\d+:\\d+,\\d+[+-]\\d+:\\d+)?(.*\\[Hardware Error\\]: Corrected error.*)'), message='RAS Corrected Error', event_category=<EventCategory.RAS: 'RAS'>, event_priority=<EventPriority.ERROR: 3>), ErrorRegex(regex=re.compile('x86/cpu: SGX disabled by BIOS'), message='SGX Error', event_category=<EventCategory.BIOS: 'BIOS'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('amdgpu \\w{4}:\\w{2}:\\w{2}.\\w: amdgpu: WARN: GPU is throttled.*'), message='GPU Throttled', event_category=<EventCategory.SW_DRIVER: 'SW_DRIVER'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:.*ko2iblnd:\\s*No matching interfaces', re.IGNORECASE), message='LNet: ko2iblnd has no matching interfaces', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('(?:\\[[^\\]]+\\]\\s*)?LNetError:\\s*.*Error\\s*-?\\d+\\s+starting up LNI\\s+\\w+', re.IGNORECASE), message='LNet: Error starting up LNI', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.WARNING: 2>), ErrorRegex(regex=re.compile('LustreError:.*ptlrpc_init_portals\\(\\).*network initiali[sz]ation failed', re.IGNORECASE), message='Lustre: network initialisation failed', event_category=<EventCategory.IO: 'IO'>, event_priority=<EventPriority.WARNING: 2>)]`

### Required Data

-

## Data Analyzer Class KernelAnalyzer

### Description

Check kernel matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/kernel/kernel_analyzer.py

### Required Data

-

## Data Analyzer Class KernelModuleAnalyzer

### Description

Check kernel matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/kernel_module/kernel_module_analyzer.py

### Required Data

-

## Data Analyzer Class MemoryAnalyzer

### Description

Check memory usage is within the maximum allowed used memory

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/memory/memory_analyzer.py

### Required Data

-

## Data Analyzer Class OsAnalyzer

### Description

Check os matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/os/os_analyzer.py

### Required Data

-

## Data Analyzer Class PackageAnalyzer

### Description

Check the package version data against the expected package version data

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/package/package_analyzer.py

### Required Data

-

## Data Analyzer Class ProcessAnalyzer

### Description

Check cpu and kfd processes are within allowed maximum cpu and gpu usage

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/process/process_analyzer.py

### Required Data

-

## Data Analyzer Class RocmAnalyzer

### Description

Check ROCm matches expected versions

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/rocm/rocm_analyzer.py

### Required Data

-

## Data Analyzer Class StorageAnalyzer

### Description

Check storage usage

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/storage/storage_analyzer.py

### Required Data

-

## Data Analyzer Class SysctlAnalyzer

### Description

Check sysctl matches expected sysctl details

**Bases**: ['DataAnalyzer']

**Link to code**: ../nodescraper/plugins/inband/sysctl/sysctl_analyzer.py

### Required Data

-

# Analyzer Args

## Analyzer Args Class BiosAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/bios/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **exp_bios_version**: `list[str]`
- **regex_match**: `<class 'bool'>`

## Analyzer Args Class CmdlineAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/cmdline/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **required_cmdline**: `str | list`
- **banned_cmdline**: `str | list`

## Analyzer Args Class DkmsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/dkms/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **dkms_status**: `str | list`
- **dkms_version**: `str | list`
- **regex_match**: `<class 'bool'>`

## Analyzer Args Class KernelAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/kernel/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **exp_kernel**: `str | list`
- **regex_match**: `<class 'bool'>`

## Analyzer Args Class KernelModuleAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/kernel_module/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **kernel_modules**: `dict[str, dict]`
- **regex_filter**: `list[str]`

## Analyzer Args Class OsAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/os/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **exp_os**: `str | list`
- **exact_match**: `<class 'bool'>`

## Analyzer Args Class PackageAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/package/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **exp_package_ver**: `dict[str, str | None]`
- **regex_match**: `<class 'bool'>`

## Analyzer Args Class ProcessAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/process/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **max_kfd_processes**: `<class 'int'>`
- **max_cpu_usage**: `<class 'float'>`

## Analyzer Args Class RocmAnalyzerArgs

**Bases**: ['BaseModel']

**Link to code**: ../nodescraper/plugins/inband/rocm/analyzer_args.py

### Class Variables

- **model_config**: `{}`

### Annotations / fields

- **exp_rocm**: `str | list`

## Analyzer Args Class SysctlAnalyzerArgs

**Bases**: ['AnalyzerArgs']

**Link to code**: ../nodescraper/plugins/inband/sysctl/analyzer_args.py

### Class Variables

- **model_config**: `{'extra': 'forbid', 'exclude_none': True}`

### Annotations / fields

- **exp_vm_swappiness**: `typing.Optional[int]`
- **exp_vm_numa_balancing**: `typing.Optional[int]`
- **exp_vm_oom_kill_allocating_task**: `typing.Optional[int]`
- **exp_vm_compaction_proactiveness**: `typing.Optional[int]`
- **exp_vm_compact_unevictable_allowed**: `typing.Optional[int]`
- **exp_vm_extfrag_threshold**: `typing.Optional[int]`
- **exp_vm_zone_reclaim_mode**: `typing.Optional[int]`
- **exp_vm_dirty_background_ratio**: `typing.Optional[int]`
- **exp_vm_dirty_ratio**: `typing.Optional[int]`
- **exp_vm_dirty_writeback_centisecs**: `typing.Optional[int]`
- **exp_kernel_numa_balancing**: `typing.Optional[int]`
